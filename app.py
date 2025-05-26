from flask import Flask, request, jsonify, render_template, session
import random
import json
import sys

# --- Flask アプリケーションのインスタンス作成 ---
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用の秘密鍵

# --- ゲーム設定 ---
DECK = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # 1～11のカードが1枚ずつ
BURST_LIMIT = 21
INITIAL_POINTS = 10


# --- 勝敗が決まったときにどれだけポイントを増減させるかを決めるための定数
POINT_CHANGE_ON_WIN = 1   # 勝利時のポイント増加量
POINT_CHANGE_ON_LOSE = -1 # 敗北時のポイント減少量 (負の値)

# --- SPカード設定 ---
# SPカードの種類や効果を定義するマスター辞書
# キー: SPカードを一意に識別するID (例: 'sp_minus_3')
# 値: カードの詳細情報を含む辞書
SP_CARDS_MASTER = {
    "sp_minus_3": {             # このカードのID
        "name": "ポイント-3",      # 画面に表示する名前
        "effect_value": -3,       # 効果の値 (相手ポイントを3減らす)
        "target": "opponent",     # 効果の対象 ('opponent' or 'self')
        "description": "相手のポイントを3減らす" # 簡単な説明
    }
    # 将来、ここに新しいSPカードを追加できます
    # "sp_heal_1": { "name": "回復+1", "effect_value": 1, "target": "self", "description": "自分のポイントを1回復" },
}

# ゲーム開始時にプレイヤーに配布するSPカードのID (今回は固定で1枚)
INITIAL_PLAYER_SP_CARD_ID = "sp_minus_3"


# --- ユーティリティ関数 ---
def calculate_total(hand):
    """手札の合計値を単純に計算（各カードの数値をそのまま採用）"""
    return sum(hand)

def shuffle_deck():
    """デッキをシャッフルして返す"""
    deck = DECK[:]
    random.shuffle(deck)
    return deck

def compute_intermediate_reward(prev_total, new_total):
    """
    カードを引いた後の中間報酬を計算する関数。
    新しい合計が増えていれば 0.1 の報酬を与え、
    バーストの場合は後で大きなペナルティを与えるためここでは 0 とする。
    """
    if new_total > BURST_LIMIT:
        return 0
    return 0.1 if new_total > prev_total else 0

def compute_final_reward(agent_total, opponent_total):
    """
    ゲーム終了時の報酬を計算する関数。
    21に近いほど有利とみなし、差分に応じた正負の報酬を返す。
    """
    diff_agent = BURST_LIMIT - agent_total
    diff_opponent = BURST_LIMIT - opponent_total if opponent_total <= BURST_LIMIT else 999
    if diff_agent < diff_opponent:
        return diff_opponent - diff_agent
    elif diff_agent > diff_opponent:
        return -(diff_agent - diff_opponent)
    else:
        return 0


def judge(player_total, ai_total):
    """
    勝敗判定：
      - プレイヤーがバーストなら -1
      - AIがバーストなら 1
      - 同点なら 0
      - それ以外は、21に近いほうが勝ち
    """
    if player_total > BURST_LIMIT:
        return -1
    if ai_total > BURST_LIMIT:
        return 1
    if player_total == ai_total:
        return 0
    return 1 if player_total > ai_total else -1

# --- 改良版 OmegaAI (ルールベース) 部 ---
def calculate_expected_value(hand, deck):
    """
    現在の手札に対し、残りデッキから1枚引いた場合の期待値と
    バースト（合計21超え）の確率を算出する。
    """
    n = len(deck)
    if n == 0:
        return None, None
    total_sum = 0
    burst_count = 0
    for card in deck:
        new_total = calculate_total(hand + [card])
        total_sum += new_total
        if new_total > BURST_LIMIT:
            burst_count += 1
    expected_value = total_sum / n
    burst_probability = burst_count / n
    return expected_value, burst_probability

def calculate_burst_probability(hand, deck):
    """
    現在の手札に対し、残りデッキから1枚引いた場合のバースト確率を返す。
    """
    n = len(deck)
    if n == 0:
        return 0.0
    burst_count = sum(1 for card in deck if calculate_total(hand + [card]) > BURST_LIMIT)
    return burst_count / n

def compute_risk_tolerance(ai_total, opponent_total, deck):
    """
    AIの現在の合計(ai_total)と対戦相手の合計(opponent_total)、残りカード枚数(deck)から
    リスク許容度の閾値を算出する。
    """
    base_threshold = 17
    risk_tolerance = base_threshold
    if opponent_total >= 17:
        risk_tolerance = max(risk_tolerance - 2, 15)
    if ai_total < 10:
        risk_tolerance -= 2
    risk_tolerance += len(deck) / 11.0
    return risk_tolerance

def should_ai_draw(ai_hand, opponent_hand, deck):
    """
    通常ターンでのAI判断ロジック：
      - 手札合計が12未満なら無条件ヒット
      - 期待値・バースト確率、リスク許容度に基づきヒット/スタンドを判断
    """
    ai_total = calculate_total(ai_hand)
    opponent_total = calculate_total(opponent_hand)
    if ai_total < 12:
        return True
    expected_value, burst_probability = calculate_expected_value(ai_hand, deck)
    if expected_value is None:
        return False
    risk_tolerance = compute_risk_tolerance(ai_total, opponent_total, deck)
    if ai_total < risk_tolerance and burst_probability < 0.30:
        return True
    if ai_total < opponent_total and burst_probability < 0.25:
        return True
    return False

def should_ai_draw_first_turn(ai_hand, opponent_hand, deck):
    """
    初手時のAI判断：
      - 初手カードが6以下なら積極的にヒット
      - それ以外は期待値に基づいて判断
    """
    if ai_hand[0] <= 6:
        return True
    else:
        expected_value, _ = calculate_expected_value(ai_hand, deck)
        return True if (expected_value is not None and expected_value < 17) else False

# --- Q学習エージェント部 (0302改良版) ---
class QLearningAgent:
    def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.3, epsilon_decay=0.99999, min_epsilon=0.01, reward_scale=1.0):
        self.q_table = {}
        self.alpha = alpha              # 学習率
        self.gamma = gamma              # 割引率
        self.epsilon = epsilon          # 初期探索率
        self.epsilon_decay = epsilon_decay  # ε減衰係数（エピソード毎に掛ける）
        self.min_epsilon = min_epsilon      # εの下限
        self.reward_scale = reward_scale    # 報酬スケーリング係数

    def get_state(self, player_total, opponent_card, deck):
        """
        状態表現：
         - プレイヤーの合計
         - 相手のオープンカード
         - 残りカード (1～11) の各枚数を '_' で連結した文字列
        """
        deck_counts = [str(deck.count(i)) for i in range(1, 12)]
        deck_info = "_".join(deck_counts)
        return f"{player_total}_{opponent_card}_{deck_info}"

    def choose_action(self, state):
        """
        ε-greedy によるアクション選択：
         - 未学習状態の場合、初期化後ランダム選択（"hit" と "stand" のどちらか）
         - εの確率でランダムに行動を選択し、それ以外はQ値最大の行動を返す
        """
        if state not in self.q_table:
            self.q_table[state] = {"hit": 0.0, "stand": 0.0}
        if random.uniform(0, 1) < self.epsilon:
            return random.choice(["hit", "stand"])
        return max(self.q_table[state], key=self.q_table[state].get)

    def learn(self, state, action, reward, next_state):
        """
        Q値の更新：
         - 報酬は reward_scale によってスケーリング
         - 次状態の最大Q値を利用して更新（終端状態の場合 next_state は None）
        """
        reward *= self.reward_scale
        if state not in self.q_table:
            self.q_table[state] = {"hit": 0.0, "stand": 0.0}
        next_max = 0
        if next_state and next_state in self.q_table:
            next_max = max(self.q_table[next_state].values())
        self.q_table[state][action] += self.alpha * (reward + self.gamma * next_max - self.q_table[state][action])

    def decay_epsilon(self):
        """
        エピソード終了毎に ε を減衰させ、探索から活用へシフト
        """
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)

    def save(self, filename="q_table.json"):
        with open(filename, 'w') as f:
            json.dump(self.q_table, f, indent=4)

    def load(self, filename="q_table.json"):
        try:
            with open(filename, 'r') as f:
                self.q_table = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("Qテーブルファイルが見つからないか、空または壊れています。")


# --- 学習モード Phase1: OmegaAI vs Q学習 ---
def train_phase1(agent, episodes=2000000):
    max_iterations = 50  # 1ゲームあたりの最大ラウンド数
    for episode in range(episodes):
        deck = shuffle_deck()
        # 初期カード：QエージェントとOmegaAIに1枚ずつ配布
        q_hand = [deck.pop()]
        opponent_hand = [deck.pop()]
        player_stand_count = 0
        ai_stand_count = 0
        iteration = 0
        state = None
        action = None
        prev_total = calculate_total(q_hand)

        while iteration < max_iterations:
            iteration += 1
            # ----- Q学習エージェントのターン -----
            q_total = calculate_total(q_hand)
            state = agent.get_state(q_total, opponent_hand[0], deck)
            action = agent.choose_action(state)
            if action == "hit":
                if deck:
                    q_hand.append(deck.pop())
                player_stand_count = 0
                new_total = calculate_total(q_hand)
                intermediate_reward = compute_intermediate_reward(q_total, new_total)
                agent.learn(state, action, intermediate_reward, None)
                q_total = new_total
                if q_total > BURST_LIMIT:
                    agent.learn(state, action, -10, None)
                    break  # ゲーム終了（バースト）
                prev_total = q_total
            else:
                player_stand_count += 1

            # ----- OmegaAI のターン -----
            opponent_total = calculate_total(opponent_hand)
            if iteration == 1:
                ai_action = "hit" if should_ai_draw_first_turn(opponent_hand, q_hand, deck) else "stand"
            else:
                ai_action = "hit" if should_ai_draw(opponent_hand, q_hand, deck) else "stand"
            if ai_action == "hit":
                if deck:
                    opponent_hand.append(deck.pop())
                ai_stand_count = 0
                opponent_total = calculate_total(opponent_hand)
                if opponent_total > BURST_LIMIT:
                    # OmegaAIがバーストした場合、Qエージェントへ報酬を与える
                    reward = 10 + (BURST_LIMIT - calculate_total(q_hand))
                    agent.learn(state, action, reward, None)
                    break  # ゲーム終了
            else:
                ai_stand_count += 1

            # ----- 両者の連続スタンドチェック -----
            if ai_stand_count >= 3:
                final_reward = compute_final_reward(q_total, opponent_total)
                agent.learn(state, action, final_reward, None)
                break

        agent.decay_epsilon()  # 各エピソード終了毎にεを減衰
        if (episode + 1) % 500 == 0:
            print(f"Phase1: {episode + 1}エピソード終了")
    agent.save("q_table.json")


# --- 学習モード Phase2: Q学習 vs Q学習 ---
def simulate_q_vs_q(agent, episodes=1000000):
    max_iterations = 50
    results = {"agent1_win": 0, "agent2_win": 0, "draw": 0}
    for _ in range(episodes):
        deck = shuffle_deck()
        agent1_hand = [deck.pop(), deck.pop()]
        agent2_hand = [deck.pop(), deck.pop()]
        stand_count1 = 0
        stand_count2 = 0
        iteration = 0
        # 各エージェントの状態・行動の記録リスト
        transitions1 = []
        transitions2 = []
        
        while iteration < max_iterations:
            iteration += 1
            # Agent1 のターン
            total1 = calculate_total(agent1_hand)
            state1 = agent.get_state(total1, agent2_hand[0], deck)
            action1 = agent.choose_action(state1)
            transitions1.append((state1, action1))
            if action1 == "hit":
                if deck:
                    agent1_hand.append(deck.pop())
                stand_count1 = 0
            else:
                stand_count1 += 1

            # Agent2 のターン
            total2 = calculate_total(agent2_hand)
            state2 = agent.get_state(total2, agent1_hand[0], deck)
            action2 = agent.choose_action(state2)
            transitions2.append((state2, action2))
            if action2 == "hit":
                if deck:
                    agent2_hand.append(deck.pop())
                stand_count2 = 0
            else:
                stand_count2 += 1

            if stand_count1 >= 3 or stand_count2 >= 3:
                break

        total1 = calculate_total(agent1_hand)
        total2 = calculate_total(agent2_hand)
        # 勝敗判定と結果の記録
        if total1 > BURST_LIMIT and total2 > BURST_LIMIT:
            outcome = 0  # 引き分け
            results["draw"] += 1
        elif total1 > BURST_LIMIT:
            outcome = -1  # Agent2 の勝ち
            results["agent2_win"] += 1
        elif total2 > BURST_LIMIT:
            outcome = 1   # Agent1 の勝ち
            results["agent1_win"] += 1
        else:
            outcome = judge(total1, total2)  # 1: Agent1勝利, -1: Agent2勝利, 0: 引き分け
            if outcome == 1:
                results["agent1_win"] += 1
            elif outcome == -1:
                results["agent2_win"] += 1
            else:
                results["draw"] += 1

        # 結果に基づく報酬設定
        reward_agent1 = 1 if outcome == 1 else (-1 if outcome == -1 else 0)
        reward_agent2 = 1 if outcome == -1 else (-1 if outcome == 1 else 0)
        
        # 記録された各遷移に対して、最終報酬を用いたQテーブルの更新（終端状態なので next_state は None）
        for (state, action) in transitions1:
            agent.learn(state, action, reward_agent1, None)
        for (state, action) in transitions2:
            agent.learn(state, action, reward_agent2, None)
            
        agent.decay_epsilon()  # 各エピソード終了毎にεを減衰

    return results

# --- Q学習エージェントの初期化と読み込み ---
agent = QLearningAgent()
agent.load()

# --- API エンドポイント ---
@app.route("/")
def index():
    """トップページ (ゲーム選択)"""
    return render_template("index.html")



@app.route("/start_game", methods=["POST"])
def start_game():
    """
    ゲーム開始：
      - ポイント、SPカードは維持しつつ、デッキ、手札などを初期化
    """
    # --- ポイント初期化（初回のみ）---
    if 'player_points' not in session:
        session['player_points'] = INITIAL_POINTS
        print("Initializing player points.")
    if 'ai_points' not in session:
        session['ai_points'] = INITIAL_POINTS
        print("Initializing AI points.")

    # --- SPカード配布（★★★ 毎回補充するように変更 ★★★） ---
    # プレイヤーへの配布
    if 'player_sp_cards' not in session: # 初回のみ辞書を初期化
        session['player_sp_cards'] = {}
    card_id_to_give = INITIAL_PLAYER_SP_CARD_ID
    if card_id_to_give in SP_CARDS_MASTER:
        # .get(key, 0) で枚数を取得し、1増やす
        current_amount = session['player_sp_cards'].get(card_id_to_give, 0)
        session['player_sp_cards'][card_id_to_give] = current_amount + 1 # ★ 単純に1増やす ★
        session.modified = True
        print(f"Gave SP card {card_id_to_give} to player. Total: {session['player_sp_cards'][card_id_to_give]}") # デバッグ用
    else:
        print(f"警告: 配布しようとしたSPカードID '{card_id_to_give}' がマスターに存在しません。")

    # AIへの配布
    if 'ai_sp_cards' not in session: # 初回のみ辞書を初期化
        session['ai_sp_cards'] = {}
    # card_id_to_give はプレイヤーと同じものを使用
    if card_id_to_give in SP_CARDS_MASTER:
        # .get(key, 0) で枚数を取得し、1増やす
        current_amount_ai = session['ai_sp_cards'].get(card_id_to_give, 0)
        session['ai_sp_cards'][card_id_to_give] = current_amount_ai + 1 # ★ 単純に1増やす ★
        session.modified = True
        print(f"Gave SP card {card_id_to_give} to AI. Total: {session['ai_sp_cards'][card_id_to_give]}") # デバッグ用
    # --- ★★★ ここまで変更 ★★★ ---

    # --- デッキと手札の準備 ---
    session["deck"] = shuffle_deck()
    if len(session["deck"]) < 4:
        return jsonify({
            "error": "Not enough cards in the deck.",
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
        }), 500

    session["player_hand"] = [session["deck"].pop(), session["deck"].pop()]
    session["ai_hand"] = [session["deck"].pop(), session["deck"].pop()]

    # --- ゲーム状態リセット ---
    session["player_stand"] = False
    session["player_consecutive_stand"] = 0
    session["ai_consecutive_stand"] = 0
    session["turn"] = "player"
    session.pop('declared_sp_card', None)
    session.pop('ai_declared_sp_card', None)
    # session.modified = True # 不要なら削除

    load_status = "学習済みファイルを読み込みました。" if agent.q_table else "学習済みファイルが空です。"

    
    # ゲーム開始時は game_over: False なので、最初のカードを隠す
    try:
        # ai_hand が確実に存在し、要素が2つ以上あることを確認
        if session.get("ai_hand") and len(session["ai_hand"]) >= 1:
             ai_hand_display = [0] + session["ai_hand"][1:] # 最初のカードを0に置き換え
        else:
             ai_hand_display = [] # もしai_handがおかしい場合は空リスト
    except Exception as e:
        print(f"Error creating ai_hand_display in start_game: {e}")
        ai_hand_display = [] # エラー時も空リスト


    # --- レスポンス ---
    return jsonify({
        "player_hand": session["player_hand"],
        "ai_hand": ai_hand_display, # ★★★ 作成した ai_hand_display を渡す ★★★
        "player_points": session.get('player_points', INITIAL_POINTS),
        "ai_points": session.get('ai_points', INITIAL_POINTS),
        "player_sp_cards": session.get('player_sp_cards', {}),
        "ai_sp_cards": session.get('ai_sp_cards', {}),
        "declared_sp_card": session.get('declared_sp_card'),
        "ai_declared_sp_card": session.get('ai_declared_sp_card'),
        "game_over": False,
        "load_status": load_status,
        "message": "ゲーム開始！あなたのターンです。"
    })


@app.route("/hit", methods=["POST"])
def hit():
    """プレイヤーがヒット"""
    print(f"--- HIT request received. Current turn in session: {session.get('turn')}")
    if session.get("turn") == "player":
        if not session["deck"]:
            return jsonify({
                "error": "No more cards in the deck.",
                "player_points": session.get('player_points', INITIAL_POINTS),
                "ai_points": session.get('ai_points', INITIAL_POINTS),
                "player_sp_cards": session.get('player_sp_cards', {}),
                "ai_sp_cards": session.get('ai_sp_cards', {}),
            }), 400

        session["player_hand"].append(session["deck"].pop())
        session["player_consecutive_stand"] = 0
        player_total = calculate_total(session["player_hand"])
        message = f"あなたがヒットしました。合計: {player_total}" # ベースメッセージ

        if player_total > BURST_LIMIT: # プレイヤーバースト (AI勝利)
            print(f"Player burst. Setting turn to 'end'")
            session["turn"] = "end"

            # ポイント更新 (Player Lose, AI Win)
            player_current_points = session.get('player_points', INITIAL_POINTS)
            ai_current_points = session.get('ai_points', INITIAL_POINTS)
            session['player_points'] = player_current_points + POINT_CHANGE_ON_LOSE
            session['ai_points'] = ai_current_points + POINT_CHANGE_ON_WIN

            # プレイヤー宣言クリア (効果なし)
            declared_card_id_player = session.pop('declared_sp_card', None)
            if declared_card_id_player:
                print(f"Player lost, Player's declared card '{declared_card_id_player}' effect not applied.")

            # AI宣言効果適用
            ai_declared_card_id = session.pop('ai_declared_sp_card', None)
            sp_effect_message_ai = ""
            if ai_declared_card_id and ai_declared_card_id in SP_CARDS_MASTER:
                card_info = SP_CARDS_MASTER[ai_declared_card_id]
                effect_value = card_info.get("effect_value", 0)
                target = card_info.get("target", "opponent")
                if target == "opponent": # プレイヤー対象
                    if 'player_points' not in session: session['player_points'] = INITIAL_POINTS
                    original_player_points = session['player_points']
                    session['player_points'] += effect_value # プレイヤーポイント減少
                    sp_effect_message_ai = f"\nさらにAIが宣言していた'{card_info.get('name', ai_declared_card_id)}'の効果発動！ あなたのポイント {original_player_points} → {session['player_points']}"
                    print(f"AI won (Player burst), AI's declared card '{ai_declared_card_id}' effect applied to Player.")
            elif ai_declared_card_id:
                 print(f"AI won, but AI's declared card '{ai_declared_card_id}' invalid or effect not applicable.")

            # メッセージ組み立て
            message = f"あなたがヒットしました。合計: {player_total}\nあなたはバーストしました！AIの勝ち！ ({POINT_CHANGE_ON_LOSE}ポイント)"
            message += sp_effect_message_ai # AIの効果メッセージ追加
            game_over_message = ""
            if session['player_points'] <= 0:
                 game_over_message = "\nあなたのポイントが0になりました。ゲームオーバー！"
            if session['ai_points'] <= 0: # AIポイント0チェックも念のため
                 game_over_message += "\nAIのポイントが0になりました。あなたの完全勝利！"
            message += game_over_message

            # ★★★ ゲームオーバーなので、実際のAI手札をそのまま返す ★★★
            ai_hand_to_return = session.get("ai_hand", []) # sessionから実際のai_handを取得

            return jsonify({
                "player_hand": session["player_hand"],
                "ai_hand": ai_hand_to_return, # ★ 実際のAI手札 ★
                "player_points": session['player_points'],
                "ai_points": session['ai_points'],
                "player_sp_cards": session.get('player_sp_cards', {}),
                "ai_sp_cards": session.get('ai_sp_cards', {}),
                "declared_sp_card": None,
                "ai_declared_sp_card": session.get('ai_declared_sp_card'), # AI宣言はまだクリアしない
                "game_over": True,
                "message": message
            })

        else: # --- ヒット成功時 ---
            print(f"Hit successful. Setting turn to 'ai'")
            session["turn"] = "ai"

            # --- ↓↓↓ レスポンス作成前に ai_hand_display を作成 ↓↓↓ ---
            # ゲーム継続中なので、最初のカードを隠す
            try:
                if session.get("ai_hand") and len(session["ai_hand"]) >= 1:
                     ai_hand_display = [0] + session["ai_hand"][1:]
                else:
                     ai_hand_display = []
            except Exception as e:
                print(f"Error creating ai_hand_display in hit (success): {e}")
                ai_hand_display = []
            # --- ↑↑↑ レスポンス作成前に ai_hand_display を作成 ↑↑↑ ---

            return jsonify({
                "player_hand": session["player_hand"],
                "ai_hand": ai_hand_display, # ★ 隠したAI手札 ★
                "player_points": session.get('player_points', INITIAL_POINTS),
                "ai_points": session.get('ai_points', INITIAL_POINTS),
                "player_sp_cards": session.get('player_sp_cards', {}),
                "ai_sp_cards": session.get('ai_sp_cards', {}),
                "declared_sp_card": session.get('declared_sp_card'),
                "ai_declared_sp_card": session.get('ai_declared_sp_card'),
                "game_over": False,
                "message": message
            })

    else: # --- "Not your turn" の場合 ---
        # --- ↓↓↓ レスポンス作成前に ai_hand_display を作成 ↓↓↓ ---
        # ゲームは継続中とみなして、最初のカードを隠す
        try:
            current_ai_hand = session.get("ai_hand", [])
            if current_ai_hand and len(current_ai_hand) >= 1:
                 ai_hand_display = [0] + current_ai_hand[1:]
            else:
                 ai_hand_display = []
        except Exception as e:
            print(f"Error creating ai_hand_display in hit (not your turn): {e}")
            ai_hand_display = []
        # --- ↑↑↑ レスポンス作成前に ai_hand_display を作成 ↑↑↑ ---

        return jsonify({
            "message": "Not your turn",
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "player_hand": session.get("player_hand", []),
            "ai_hand": ai_hand_display, # ★ 隠したAI手札 ★
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            # "game_over": False, # 返さなくても良いかも
        })


@app.route("/stand", methods=["POST"])
def stand():
    """プレイヤーがスタンド"""
    print(f"--- STAND request received. Current turn in session: {session.get('turn')}")
    if session.get("turn") == "player":
        session["player_consecutive_stand"] = session.get("player_consecutive_stand", 0) + 1
        print(f"Stand successful. Setting turn to 'ai'")
        session["turn"] = "ai"
        message = "あなたがスタンドしました。AIのターンです。"

        # --- ↓↓↓ レスポンス作成前に ai_hand_display を作成 ↓↓↓ ---
        # ゲーム継続中なので、最初のカードを隠す
        try:
            if session.get("ai_hand") and len(session["ai_hand"]) >= 1:
                 ai_hand_display = [0] + session["ai_hand"][1:]
            else:
                 ai_hand_display = []
        except Exception as e:
            print(f"Error creating ai_hand_display in stand (success): {e}")
            ai_hand_display = []
        # --- ↑↑↑ レスポンス作成前に ai_hand_display を作成 ↑↑↑ ---

        # ★ スタンド時のレスポンスを変更 ★
        return jsonify({
            "player_hand": session["player_hand"],
            "ai_hand": ai_hand_display, # ★ 隠したAI手札 ★
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            "game_over": False,
            "message": message,
        })

    else: # --- "Not your turn" の場合 ---
        # --- ↓↓↓ レスポンス作成前に ai_hand_display を作成 ↓↓↓ ---
        # ゲームは継続中とみなして、最初のカードを隠す
        try:
            current_ai_hand = session.get("ai_hand", [])
            if current_ai_hand and len(current_ai_hand) >= 1:
                 ai_hand_display = [0] + current_ai_hand[1:]
            else:
                 ai_hand_display = []
        except Exception as e:
            print(f"Error creating ai_hand_display in stand (not your turn): {e}")
            ai_hand_display = []
        # --- ↑↑↑ レスポンス作成前に ai_hand_display を作成 ↑↑↑ ---

        return jsonify({
            "message": "Not your turn",
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "player_hand": session.get("player_hand", []),
            "ai_hand": ai_hand_display, # ★ 隠したAI手札 ★
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
        })


@app.route("/ai_turn", methods=["POST"])
def ai_turn():
    """AIのターン"""
    print(f"--- AI_TURN request received. Current turn in session: {session.get('turn')}")
    if session.get("turn") == "ai":
        # --- AIのSPカード使用宣言判断 ---
        ai_declared_card_this_turn = None
        ai_declare_message = "" # AI宣言メッセージ初期化 (ここで初期化)
        if not session.get('ai_declared_sp_card') and not session.get('declared_sp_card'):
            ai_hand = session["ai_hand"]
            player_hand = session["player_hand"]
            ai_sp_cards = session.get('ai_sp_cards', {})
            ai_total = calculate_total(ai_hand)
            player_open_card = player_hand[0]

            # ★★★ AIのSPカード使用判断ルール (シンプル版) ★★★
            card_to_declare = None # ★★★ 変数をNoneで初期化 ★★★
            # 例: AI合計18以上、相手オープンカード7以下、かつポイント-3カードを持っている場合
            if ai_total >= 18 and player_open_card <= 7 and ai_sp_cards.get("sp_minus_3", 0) > 0:
                card_to_declare = "sp_minus_3"

            # --- もし使用宣言すると判断した場合 ---
            if card_to_declare:
                print(f"AI decided to declare SP card: {card_to_declare}")
                # カードを消費
                ai_sp_cards[card_to_declare] -= 1
                session['ai_sp_cards'] = ai_sp_cards
                # 宣言状態を記録
                session['ai_declared_sp_card'] = card_to_declare
                session.modified = True
                ai_declared_card_this_turn = card_to_declare
                # AI宣言メッセージを作成
                card_name = SP_CARDS_MASTER.get(ai_declared_card_this_turn, {}).get('name', ai_declared_card_this_turn)
                ai_declare_message = f"\nAIは '{card_name}' の使用を宣言しました！ (カード消費済み)"
        # --- ここまでSPカード宣言判断 ---

        # --- AIのヒット/スタンドアクション選択 ---
        # AIの手札合計を再計算 (SPカード判断で手札が変わることはないが念のため)
        ai_total = calculate_total(session["ai_hand"])
        player_open_card = session["player_hand"][0]
        state = agent.get_state(ai_total, player_open_card, session["deck"])
        action = agent.choose_action(state)
        message = "" # メインメッセージ初期化

        if action == "hit": # --- AIがヒットした場合 ---
            if not session["deck"]: # デッキ切れの場合 (game_over: False)
                session["turn"] = "player"
                message = "AI: ヒットしたかったがデッキ切れ。あなたのターンです。"
                try:
                    ai_hand_display = [0] + session["ai_hand"][1:] if session.get("ai_hand") and len(session["ai_hand"]) >= 1 else []
                except Exception as e:
                    print(f"Error creating ai_hand_display in ai_turn (deck empty): {e}")
                    ai_hand_display = []
                return jsonify({
                    "player_hand": session["player_hand"],
                    "ai_hand": ai_hand_display,
                    "player_points": session.get('player_points', INITIAL_POINTS),
                    "ai_points": session.get('ai_points', INITIAL_POINTS),
                    "player_sp_cards": session.get('player_sp_cards', {}),
                    "ai_sp_cards": session.get('ai_sp_cards', {}),
                    "declared_sp_card": session.get('declared_sp_card'),
                    "ai_declared_sp_card": session.get('ai_declared_sp_card'),
                    "game_over": False,
                    "message": message + ai_declare_message # AI宣言メッセージも追加
                })

            session["ai_hand"].append(session["deck"].pop())
            session["ai_consecutive_stand"] = 0
            new_ai_total = calculate_total(session["ai_hand"])
            message = f"AI: ヒット。合計: {new_ai_total}"

            if new_ai_total > BURST_LIMIT: # AIがバーストした場合 (game_over: True)
                print(f"AI burst. Setting turn to 'end'")
                session["turn"] = "end"

                # --- ポイント更新処理 (Player Win, AI Lose) ---
                player_current_points = session.get('player_points', INITIAL_POINTS)
                ai_current_points = session.get('ai_points', INITIAL_POINTS)
                session['player_points'] = player_current_points + POINT_CHANGE_ON_WIN
                session['ai_points'] = ai_current_points + POINT_CHANGE_ON_LOSE

                # --- メッセージの基本部分作成 ---
                message += f"\nAIがバーストしました！あなたの勝ち！ (+{POINT_CHANGE_ON_WIN}ポイント)" # message に追記する形に変更

                # --- プレイヤーのSPカード効果適用処理 ---
                declared_card_id = session.pop('declared_sp_card', None)
                sp_effect_message = ""
                if declared_card_id and declared_card_id in SP_CARDS_MASTER:
                    card_info = SP_CARDS_MASTER[declared_card_id]
                    effect_value = card_info.get("effect_value", 0)
                    target = card_info.get("target", "opponent")
                    if target == "opponent":
                        if 'ai_points' not in session: session['ai_points'] = INITIAL_POINTS
                        original_ai_points = session['ai_points']
                        session['ai_points'] += effect_value
                        sp_effect_message = f"\n宣言していた'{card_info.get('name', declared_card_id)}'の効果発動！ AIポイント {original_ai_points} → {session['ai_points']}"
                        print(f"Player won (AI burst), declared card '{declared_card_id}' effect applied to AI.")
                    else:
                         if 'player_points' not in session: session['player_points'] = INITIAL_POINTS
                         original_player_points = session['player_points']
                         session['player_points'] += effect_value
                         sp_effect_message = f"\n宣言していた'{card_info.get('name', declared_card_id)}'の効果発動！ あなたのポイント {original_player_points} → {session['player_points']}"
                         print(f"Player won (AI burst), declared card '{declared_card_id}' effect applied to Player.")
                    message += sp_effect_message
                elif declared_card_id:
                    print(f"Player won, but declared card '{declared_card_id}' not found in master or invalid.")

                # --- AI自身の宣言はクリアするだけ ---
                ai_declared_card_id_popped = session.pop('ai_declared_sp_card', None) # 変数名変更
                if ai_declared_card_id_popped:
                    print(f"AI lost (burst), AI's declared card '{ai_declared_card_id_popped}' effect not applied.")

                # --- ポイント0チェック ---
                game_over_message = ""
                if session['player_points'] <= 0:
                     game_over_message += "\nあなたのポイントが0になりました。ゲームオーバー！"
                if session['ai_points'] <= 0:
                     game_over_message += "\nAIのポイントが0になりました。あなたの完全勝利！"
                message += game_over_message

                ai_hand_to_return = session.get("ai_hand", [])

                return jsonify({
                    "player_hand": session["player_hand"],
                    "ai_hand": ai_hand_to_return,
                    "player_points": session['player_points'],
                    "ai_points": session['ai_points'],
                    "player_sp_cards": session.get('player_sp_cards', {}),
                    "ai_sp_cards": session.get('ai_sp_cards', {}),
                    "declared_sp_card": None,
                    "ai_declared_sp_card": None, # クリアされたので None
                    "game_over": True,
                    "message": message # AI宣言メッセージは含めない (バーストメッセージが主)
                })

            else: # AIヒット成功した場合 (game_over: False)
                print(f"AI hit successful. Setting turn to 'player'")
                session["turn"] = "player"
                try:
                    ai_hand_display = [0] + session["ai_hand"][1:] if session.get("ai_hand") and len(session["ai_hand"]) >= 1 else []
                except Exception as e:
                    print(f"Error creating ai_hand_display in ai_turn (hit success): {e}")
                    ai_hand_display = []
                return jsonify({
                    "player_hand": session["player_hand"],
                    "ai_hand": ai_hand_display,
                    "player_points": session.get('player_points', INITIAL_POINTS),
                    "ai_points": session.get('ai_points', INITIAL_POINTS),
                    "player_sp_cards": session.get('player_sp_cards', {}),
                    "ai_sp_cards": session.get('ai_sp_cards', {}),
                    "declared_sp_card": session.get('declared_sp_card'),
                    "ai_declared_sp_card": session.get('ai_declared_sp_card'),
                    "game_over": False,
                    "message": message + ai_declare_message + " あなたのターンです。"
                })

        else: # --- AIがスタンドした場合 ---
            session["ai_consecutive_stand"] = session.get("ai_consecutive_stand", 0) + 1
            message = "AI: スタンド。" # ベースメッセージ

            if session["ai_consecutive_stand"] >= 3: # 両者スタンド終了 (game_over: True)
                print(f"AI stand x3. Setting turn to 'end'")
                session["turn"] = "end"
                player_total = calculate_total(session["player_hand"])
                ai_total_final = calculate_total(session["ai_hand"])
                result = judge(player_total, ai_total_final)

                # --- ポイント更新処理 ---
                player_current_points = session.get('player_points', INITIAL_POINTS)
                ai_current_points = session.get('ai_points', INITIAL_POINTS)
                point_change_player = 0
                point_change_ai = 0
                result_message = ""
                if result == 1:
                    point_change_player = POINT_CHANGE_ON_WIN
                    point_change_ai = POINT_CHANGE_ON_LOSE
                    result_message = f"あなたの勝ち！ (+{point_change_player}ポイント)"
                elif result == -1:
                    point_change_player = POINT_CHANGE_ON_LOSE
                    point_change_ai = POINT_CHANGE_ON_WIN
                    result_message = f"AIの勝ち！ ({point_change_player}ポイント)"
                else:
                    result_message = "引き分け！ (ポイント変動なし)"
                session['player_points'] = player_current_points + point_change_player
                session['ai_points'] = ai_current_points + point_change_ai

                # --- プレイヤーのSPカード効果適用 or クリア ---
                declared_card_id_player = session.pop('declared_sp_card', None) # 変数名変更
                sp_effect_message_player = ""
                if result == 1 and declared_card_id_player and declared_card_id_player in SP_CARDS_MASTER:
                    card_info = SP_CARDS_MASTER[declared_card_id_player]
                    effect_value = card_info.get("effect_value", 0)
                    target = card_info.get("target", "opponent")
                    if target == "opponent":
                        if 'ai_points' not in session: session['ai_points'] = INITIAL_POINTS
                        original_ai_points = session['ai_points']
                        session['ai_points'] += effect_value
                        sp_effect_message_player = f"\n宣言していた'{card_info.get('name', declared_card_id_player)}'の効果発動！ AIポイント {original_ai_points} → {session['ai_points']}"
                        print(f"Player won (standoff), declared card '{declared_card_id_player}' effect applied to AI.")
                    else:
                         if 'player_points' not in session: session['player_points'] = INITIAL_POINTS
                         original_player_points = session['player_points']
                         session['player_points'] += effect_value
                         sp_effect_message_player = f"\n宣言していた'{card_info.get('name', declared_card_id_player)}'の効果発動！ あなたのポイント {original_player_points} → {session['player_points']}"
                         print(f"Player won (standoff), declared card '{declared_card_id_player}' effect applied to Player.")
                elif declared_card_id_player:
                    print(f"Player didn't win or card invalid, declared card '{declared_card_id_player}' effect not applied.")

                # --- AIのSPカード効果適用 or クリア ---
                ai_declared_card_id_popped = session.pop('ai_declared_sp_card', None) # 変数名変更
                sp_effect_message_ai = ""
                if result == -1 and ai_declared_card_id_popped and ai_declared_card_id_popped in SP_CARDS_MASTER:
                    card_info_ai = SP_CARDS_MASTER[ai_declared_card_id_popped]
                    effect_value_ai = card_info_ai.get("effect_value", 0)
                    target_ai = card_info_ai.get("target", "opponent")
                    if target_ai == "opponent":
                        if 'player_points' not in session: session['player_points'] = INITIAL_POINTS
                        original_player_points_ai = session['player_points']
                        session['player_points'] += effect_value_ai
                        sp_effect_message_ai = f"\nさらにAIが宣言していた'{card_info_ai.get('name', ai_declared_card_id_popped)}'の効果発動！ あなたのポイント {original_player_points_ai} → {session['player_points']}"
                        print(f"AI won (standoff), AI's declared card '{ai_declared_card_id_popped}' effect applied to Player.")
                elif ai_declared_card_id_popped:
                    print(f"AI didn't win or card invalid, AI's declared card '{ai_declared_card_id_popped}' effect not applied.")

                # --- ポイント0チェック ---
                game_over_message = ""
                if session['player_points'] <= 0:
                     game_over_message += "\nあなたのポイントが0になりました。ゲームオーバー！"
                if session['ai_points'] <= 0:
                     game_over_message += "\nAIのポイントが0になりました。あなたの完全勝利！"

                # --- 最終的なメッセージ組み立て ---
                message += f"\nゲーム終了！ {result_message}" # 勝敗結果 (ここに追加)
                message += sp_effect_message_player
                message += sp_effect_message_ai
                message += game_over_message

                ai_hand_to_return = session.get("ai_hand", [])

                return jsonify({
                    "player_hand": session["player_hand"],
                    "ai_hand": ai_hand_to_return,
                    "player_points": session['player_points'],
                    "ai_points": session['ai_points'],
                    "player_sp_cards": session.get('player_sp_cards', {}),
                    "ai_sp_cards": session.get('ai_sp_cards', {}),
                    "declared_sp_card": None,
                    "ai_declared_sp_card": None, # クリアされたので None
                    "game_over": True,
                    "message": message # AI宣言メッセージは含めない (スタンドメッセージが先頭)
                })

            else: # AIスタンド継続 (game_over: False)
                print(f"AI stand continue. Setting turn to 'player'")
                session["turn"] = "player"
                try:
                    ai_hand_display = [0] + session["ai_hand"][1:] if session.get("ai_hand") and len(session["ai_hand"]) >= 1 else []
                except Exception as e:
                    print(f"Error creating ai_hand_display in ai_turn (stand continue): {e}")
                    ai_hand_display = []
                return jsonify({
                    "player_hand": session["player_hand"],
                    "ai_hand": ai_hand_display,
                    "player_points": session.get('player_points', INITIAL_POINTS),
                    "ai_points": session.get('ai_points', INITIAL_POINTS),
                    "player_sp_cards": session.get('player_sp_cards', {}),
                    "ai_sp_cards": session.get('ai_sp_cards', {}),
                    "declared_sp_card": session.get('declared_sp_card'),
                    "ai_declared_sp_card": session.get('ai_declared_sp_card'),
                    "game_over": False,
                    "message": message + ai_declare_message + " あなたのターンです。"
                })

    # --- elif session.get("turn") == "end" や else (Not AI turn) の場合 ---
    elif session.get("turn") == "end":
        ai_hand_to_return = session.get("ai_hand", [])
        return jsonify({
            "message": "Game already over",
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "player_hand": session.get("player_hand", []),
            "ai_hand": ai_hand_to_return,
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            })
    else: # AIのターンでない場合
        ai_hand_to_return = session.get("ai_hand", [])
        return jsonify({
            "message": "Not AI turn",
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "player_hand": session.get("player_hand", []),
            "ai_hand": ai_hand_to_return,
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            })


@app.route('/use_sp_card', methods=['POST'])
def use_sp_card():
    """プレイヤーがSPカードの使用を宣言し、消費する"""
    print(f"--- USE_SP_CARD (Declare & Consume) request received. Current turn: {session.get('turn')}")

    if session.get("turn") != "player":
        return jsonify({"error": "あなたのターンではありません。"}), 400

    if session.get('declared_sp_card'):
        return jsonify({"error": "既にSPカードを使用宣言済みです。"}), 400

    # ★ AIが宣言中の場合もプレイヤーは宣言できないようにする ★
    if session.get('ai_declared_sp_card'):
        return jsonify({"error": "AIが既にSPカードを宣言中です。"}), 400

    data = request.get_json()
    card_id = data.get('card_id')

    if not card_id or card_id not in SP_CARDS_MASTER:
        return jsonify({"error": "無効なSPカードIDです。"}), 400

    player_sp_cards = session.get('player_sp_cards', {})
    if player_sp_cards.get(card_id, 0) <= 0:
        return jsonify({"error": f"'{SP_CARDS_MASTER.get(card_id, {}).get('name', card_id)}' を持っていません。"}), 400

    # カード消費
    player_sp_cards[card_id] -= 1
    session['player_sp_cards'] = player_sp_cards
    session.modified = True
    print(f"Player consumed SP card: {card_id}. Remaining: {player_sp_cards}")

    # 宣言記録
    session['declared_sp_card'] = card_id
    print(f"Player declared SP card: {card_id}")

    # メッセージとレスポンス
    card_name = SP_CARDS_MASTER.get(card_id, {}).get('name', card_id)
    message = f"'{card_name}' の使用を宣言しました。今回の勝負に勝てば効果が発動します。（カード消費済み）"
    session["turn"] = "player"

    return jsonify({
        "message": message,
        "player_points": session.get('player_points', INITIAL_POINTS),
        "ai_points": session.get('ai_points', INITIAL_POINTS),
        "player_sp_cards": session.get('player_sp_cards', {}),
        "declared_sp_card": session.get('declared_sp_card'),
        "ai_sp_cards": session.get('ai_sp_cards', {}),
        "ai_declared_sp_card": session.get('ai_declared_sp_card'),
        "game_over": False,
    })


@app.route("/train", methods=["POST"])
def train_route():
    """Phase1 学習モード実行"""
    train_phase1(agent)
    return jsonify({"message": "Phase1 学習完了 (q_table.json 生成)"})

@app.route("/train2", methods=["POST"])
def train2_route():
    """Phase2 学習モード実行"""
    simulation_results = simulate_q_vs_q(agent, episodes=500000)
    agent.save("q_table2.json")
    return jsonify({
        "message": "Phase2 学習完了 (q_table2.json 生成)",
        "simulation_results": simulation_results
    })

@app.route('/shutdown', methods=['POST'])
def shutdown():
    sys.exit(0)


@app.route('/reset_all', methods=['POST'])
def reset_all():
    """セッション情報をクリアして初期状態に戻す"""
    print("--- RESET ALL request received ---") # デバッグ用
    # session.clear() を使うと全てのセッション情報が消えます
    session.clear()
    # あるいは、特定のキーだけ削除する場合
    # session.pop('player_points', None)
    # session.pop('ai_points', None)
    # session.pop('player_sp_cards', None)
    # session.pop('ai_sp_cards', None)
    # session.pop('declared_sp_card', None)
    # session.pop('ai_declared_sp_card', None)
    # session.pop('deck', None)
    # session.pop('player_hand', None)
    # session.pop('ai_hand', None)
    # session.pop('turn', None)
    # ... など
    print("Session cleared.")
    return jsonify({"message": "セッションがリセットされました。"})


# ★★★ 最後 ★★★
if __name__ == "__main__":
    app.run(debug=True)
