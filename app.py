from flask import Flask, request, jsonify, render_template, session
import random
import json
import sys

# --- Flask アプリケーションのインスタンス作成 ---
app = Flask(__name__)
app.secret_key = 'your_super_secret_and_random_string_here'  # セッション用の秘密鍵

# --- ゲーム設定 ---
DECK = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # 1～11のカードが1枚ずつ
BURST_LIMIT = 21
INITIAL_POINTS = 10


# --- 勝敗が決まったときにどれだけポイントを増減させるかを決めるための定数
POINT_CHANGE_ON_WIN = 1   # 勝利時のポイント増加量
POINT_CHANGE_ON_LOSE = -1 # 敗北時のポイント減少量 (負の値)

# --- SPカード設定 ---
# SPカードの種類や効果を定義するマスター辞書
# キー: SPカードを一意に識別するID
# 値: カードの詳細情報を含む辞書
SP_CARDS_MASTER = {
    "sp_minus_3": {             # このカードのID
        "name": "ポイント-3",      # 画面に表示する名前
        "effect_value": -3,       # 効果の値 (相手ポイントを3減らす)
        "target": "opponent",     # 効果の対象 ('opponent' or 'self')
        "description": "相手のポイントを3減らす" 
    },
    # 将来、ここに新しいSPカードを追加
    "sp_return_last_card": {
        "name": "手札戻し",
        "effect_type": "return_last_card", # 効果の種別を識別する新しいキー
        "target": "self", # 効果は自分自身の手札に対して
        "description": "最後に引いたカード1枚を山札に戻す"
                       # 今回は「戻すだけ」でシンプルに実装
    }
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
    勝敗判定（新々ルール）：
      - 片方のみがバーストしている場合：バーストしていない方の勝ち。
      - 両者ともバーストしている、または両者ともバーストしていない場合：
          - 21からの距離が小さい方が勝ち。
          - 距離が同じ場合は引き分け。
    戻り値:
      - プレイヤー勝利: 1
      - AI勝利: -1
      - 引き分け: 0
    """
    player_is_burst = player_total > BURST_LIMIT
    ai_is_burst = ai_total > BURST_LIMIT

    # 1. 片方のみがバーストしている場合の処理
    if player_is_burst and not ai_is_burst:
        return -1 # プレイヤーバースト、AIはバーストしていない -> AI勝利
    if not player_is_burst and ai_is_burst:
        return 1  # AIバースト、プレイヤーはバーストしていない -> プレイヤー勝利

    # 2. 両者ともバーストしている、または両者ともバーストしていない場合の処理
    # この場合は、21に近い方が勝ち (以前のロジックと同じ)
    player_distance = abs(player_total - BURST_LIMIT)
    ai_distance = abs(ai_total - BURST_LIMIT)

    if player_distance < ai_distance:
        return 1  # プレイヤー勝利
    elif ai_distance < player_distance:
        return -1 # AI勝利
    else:
        return 0  # 引き分け
    

# --- 新しい決着処理関数 ---
def _finalize_round():
    """
    ラウンドの決着処理を専門に行う関数。
    勝敗判定、ポイント増減、宣言済みSPカードの効果適用を全て担当する。
    """
    player_hand = session.get("player_hand", [])
    ai_hand = session.get("ai_hand", [])
    player_total = calculate_total(player_hand)
    ai_total = calculate_total(ai_hand)

    # 1. 勝敗判定
    result = judge(player_total, ai_total) # 1: Player win, -1: AI win, 0: Draw

    # 2. 基本的なポイント増減
    player_points = session.get('player_points', INITIAL_POINTS)
    ai_points = session.get('ai_points', INITIAL_POINTS)
    
    game_result_message = ""
    final_points_change_message = ""

    if result == 1: # プレイヤーの勝ち
        player_points += POINT_CHANGE_ON_WIN
        ai_points += POINT_CHANGE_ON_LOSE
        game_result_message = "あなたの勝ち！"
        final_points_change_message = f" ({POINT_CHANGE_ON_WIN:+d}ポイント)"
    elif result == -1: # AIの勝ち
        player_points += POINT_CHANGE_ON_LOSE
        ai_points += POINT_CHANGE_ON_WIN
        game_result_message = "AIの勝ち！"
        final_points_change_message = f" ({POINT_CHANGE_ON_LOSE:+d}ポイント)"
    else: # 引き分け
        game_result_message = "引き分け！ (ポイント変動なし)"

    # 3. SPカード効果の適用
    sp_effect_message = ""
    
    # プレイヤー勝利時に、プレイヤーが宣言していたカードの効果を適用
    declared_card_player = session.pop('declared_sp_card', None)
    if result == 1 and declared_card_player and declared_card_player in SP_CARDS_MASTER:
        card_info = SP_CARDS_MASTER[declared_card_player]
        effect_value = card_info.get("effect_value", 0)
        target = card_info.get("target", "opponent")
        if target == "opponent": # 対象はAI
            original_ai_points = ai_points
            ai_points += effect_value # ★AIのポイントを実際に変更★
            sp_effect_message += f"\nあなたが宣言した'{card_info.get('name')}'の効果発動！ AIのポイントが {original_ai_points} → {ai_points} に！"

    # AI勝利時に、AIが宣言していたカードの効果を適用
    declared_card_ai = session.pop('ai_declared_sp_card', None)
    if result == -1 and declared_card_ai and declared_card_ai in SP_CARDS_MASTER:
        card_info = SP_CARDS_MASTER[declared_card_ai]
        effect_value = card_info.get("effect_value", 0)
        target = card_info.get("target", "opponent")
        if target == "opponent": # 対象はプレイヤー
            original_player_points = player_points
            player_points += effect_value # ★プレイヤーのポイントを実際に変更★
            sp_effect_message += f"\nAIが宣言した'{card_info.get('name')}'の効果発動！ あなたのポイントが {original_player_points} → {player_points} に！"

    # 4. 最終的なポイントをセッションに保存
    session['player_points'] = player_points
    session['ai_points'] = ai_points

    # 5. メッセージを組み立てる
    final_message = f"ゲーム終了！ {game_result_message}{final_points_change_message}"
    final_message += f"\n(あなたの最終合計: {player_total}, AIの最終合計: {ai_total})"
    final_message += sp_effect_message

    # 6. 完全決着メッセージ
    if session['player_points'] <= 0:
        final_message += "\nあなたのポイントが0になりました。ゲームオーバー！"
    if session['ai_points'] <= 0:
        final_message += "\nAIのポイントが0になりました。あなたの完全勝利！"

    session["turn"] = "end" # ゲーム終了状態にする
    return final_message
# ここまで

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
    def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.3, epsilon_decay=0.99999, min_epsilon=0.01, reward_scale=1.0, min_epsilon_for_play=0.0):
        self.q_table = {}
        self.alpha = alpha              # 学習率
        self.gamma = gamma              # 割引率
        self.epsilon = epsilon          # 初期探索率
        self.epsilon_decay = epsilon_decay  # ε減衰係数（エピソード毎に掛ける）
        self.min_epsilon = min_epsilon      # εの下限
        self.reward_scale = reward_scale    # 報酬スケーリング係数
        self.min_epsilon_for_play = min_epsilon_for_play # プレイ時の最小探索率

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

    def choose_action(self, state, current_total, is_training=True):
        """
        ε-greedy によるアクション選択：
         - 未学習状態の場合、初期化後ランダム選択（"hit" と "stand" のどちらか）
         - εの確率でランダムに行動を選択し、それ以外はQ値最大の行動を返す
         - current_total: 現在の手札の合計値
         - is_training: 学習モードであればTrue、プレイモードであればFalse
        """
        # --- バースト防止追加 ---
        if current_total == BURST_LIMIT: # 既に21の場合
            return "stand"
        if current_total > BURST_LIMIT: # 既にバーストしている場合
            # この状況は通常発生しないはずだが、安全策として
            return "stand" 
        # --- ここまで ---

        # 合計が8以下の場合はほぼ無条件でヒットさせる
        LOW_TOTAL_THRESHOLD = 8 # この閾値は調整可能
        if current_total <= LOW_TOTAL_THRESHOLD:
            return "hit" 
        
        # 状態が未学習の場合、Qテーブルに初期化
        if state not in self.q_table:
            self.q_table[state] = {"hit": 0.0, "stand": 0.0}
        
        # 使用するepsilonを決定
        current_epsilon_to_use = 0 # 初期値
        if is_training:
            current_epsilon_to_use = self.epsilon # 学習中は現在のepsilonを使用
        else:
            current_epsilon_to_use = self.min_epsilon_for_play # プレイ中は固定の最小値を使用

        # ε-greedy の探索部分でも、21ならスタンドを優先する (より安全に)
        if random.uniform(0, 1) < current_epsilon_to_use:
            return random.choice(["hit", "stand"])
        else:
            # Q値が最大の行動を選択
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
def train_phase1(agent, episodes=500000):
    max_iterations = 50  # 1ゲームあたりの最大ラウンド数
    for episode in range(episodes):
        deck = shuffle_deck()
        
        # 初期カード配布
        # 最低2枚のカードがデッキにあることを保証 (q_hand, opponent_hand に1枚ずつ)
        if len(deck) < 2:
            print(f"エピソード {episode + 1} スキップ: デッキのカードが不足しています。")
            continue
        q_hand = [deck.pop()]
        opponent_hand = [deck.pop()]
        
        q_agent_stand_count = 0  # Qエージェントの連続スタンド回数
        omega_ai_stand_count = 0 # OmegaAIの連続スタンド回数
        # consecutive_both_stand = 0 # 両者が連続でスタンドした回数をカウントする場合

        iteration = 0
        
        # エピソード中の遷移を一時的に保持するための変数 (Qエージェントの視点)
        last_q_agent_state = None
        last_q_agent_action = None

        game_terminated = False # ゲームが終了したかどうかのフラグ

        while iteration < max_iterations and not game_terminated:
            iteration += 1

            # ----- Q学習エージェントのターン -----
            q_total_before_action = calculate_total(q_hand)
            
            # opponent_hand[0] が存在するか確認
            opponent_up_card = opponent_hand[0] if opponent_hand else 0 # 相手の手札がなければ0など安全な値を設定

            current_q_agent_state = agent.get_state(q_total_before_action, opponent_up_card, deck)
            q_agent_action = agent.choose_action(current_q_agent_state, q_total_before_action) # is_training=True はデフォルト

            # Qエージェントの行動前の状態と行動を記録
            last_q_agent_state = current_q_agent_state
            last_q_agent_action = q_agent_action

            reward_for_q_agent = 0 # このステップでのQエージェントへの即時報酬

            if q_agent_action == "hit":
                q_agent_stand_count = 0 
                if deck:
                    q_hand.append(deck.pop())
                    new_q_total = calculate_total(q_hand)
                    # compute_intermediate_reward の値を少し大きくする案
                    # reward_for_q_agent = compute_intermediate_reward(q_total_before_action, new_q_total) 
                    # 例えば、ここで compute_intermediate_reward の代わりに直接値を設定するか、
                    # compute_intermediate_reward の実装自体を変更する。
                    # 例: ヒット成功で +0.2 や +0.5 など (compute_intermediate_reward を変更しないなら)
                    if new_q_total > q_total_before_action and new_q_total <= BURST_LIMIT:
                        reward_for_q_agent = 0.2 # ヒット成功報酬を少し上げる例
                    else:
                        reward_for_q_agent = compute_intermediate_reward(q_total_before_action, new_q_total) # 元のままか、0か
                    
                    if new_q_total > BURST_LIMIT:
                        reward_for_q_agent += -10 
                        agent.learn(last_q_agent_state, last_q_agent_action, reward_for_q_agent, None) 
                        game_terminated = True
                else:
                    q_agent_action = "stand" 
                    last_q_agent_action = "stand" 
                    q_agent_stand_count += 1 
                    # デッキ切れでヒットできなかった場合、スタンド扱い。
                    # ここでも低い手札ならペナルティを検討
                    if q_total_before_action < 8: # 例
                         reward_for_q_agent -= 0.1 # 小さなペナルティ
            
            else: # Qエージェントがスタンド
                q_agent_stand_count += 1
                reward_for_q_agent = 0 # スタンド自体の基本報酬は0
                
                # 「低い手札でスタンドした場合のペナルティ」を追加
                LOW_HAND_STAND_THRESHOLD = 8 # 例
                if q_total_before_action < LOW_HAND_STAND_THRESHOLD:
                    reward_for_q_agent -= 0.2 # 小さな負の報酬 (値は調整可能)
                    # print(f"DEBUG: QAgent stood with low hand ({q_total_before_action}), penalty: -0.2")
                # ここまで

            if game_terminated: 
                agent.decay_epsilon() 
                continue

            # ----- OmegaAI のターン -----
            omega_ai_total_before_action = calculate_total(opponent_hand)
            q_agent_current_total_for_omega = calculate_total(q_hand) # OmegaAIから見たQエージェントの合計

            # OmegaAIの行動決定 (should_ai_draw_first_turn と should_ai_draw を使用)
            # opponent_hand が空でないことを確認
            omega_ai_action = "stand" # デフォルト
            if opponent_hand:
                if iteration == 1: # 初手かどうかは iteration で判断
                    omega_ai_action = "hit" if should_ai_draw_first_turn(opponent_hand, q_hand, deck) else "stand"
                else:
                    omega_ai_action = "hit" if should_ai_draw(opponent_hand, q_hand, deck) else "stand"
            
            if omega_ai_action == "hit":
                omega_ai_stand_count = 0 # ヒットしたらスタンドカウントリセット
                if deck:
                    opponent_hand.append(deck.pop())
                    new_omega_ai_total = calculate_total(opponent_hand)
                    if new_omega_ai_total > BURST_LIMIT:
                        # OmegaAIがバースト。Qエージェントに大きな正の報酬。
                        # Qエージェントの最後の状態・行動に対して学習
                        final_reward_for_q_burst_opponent = 10 + (BURST_LIMIT - q_agent_current_total_for_omega if q_agent_current_total_for_omega <= BURST_LIMIT else 0)
                        reward_for_q_agent += final_reward_for_q_burst_opponent # ここまでの報酬に加算
                        agent.learn(last_q_agent_state, last_q_agent_action, reward_for_q_agent, None) # 終端状態
                        game_terminated = True
                        # print(f"Debug E{episode+1}-I{iteration}: OmegaAI burst. R_Q={reward_for_q_agent}")
                else:
                    # OmegaAIがヒットしたかったがデッキ切れ。
                    # OmegaAIはスタンドしたのと同じ扱い。
                    omega_ai_action = "stand" # 行動をスタンドとして扱う
                    omega_ai_stand_count += 1
            else: # OmegaAIがスタンド
                omega_ai_stand_count += 1

            if game_terminated: # OmegaAIがバーストしてゲーム終了した場合
                agent.decay_epsilon() # エピソード終了
                continue # 次のエピソードへ

            # ----- 両者の連続スタンドチェック -----
            # ルール: 「両者がスタンドを3回連続選んだ時点で勝敗判定」
            # ここでは、各プレイヤーがそれぞれ3回連続スタンドしたら、という解釈で実装を試みる。
            # もし「プレイヤーAスタンド→AIスタンド」を1セットとして3セット連続なら、別のカウンターが必要。
            # 今回は「Qエージェントが3連続スタンド OR OmegaAIが3連続スタンド」でゲーム終了とする。
            # より厳密には「Qエージェントがスタンドし、かつOmegaAIもスタンドした」という状況が
            # 3回連続した場合、というカウンター (consecutive_both_stand) を使うのがルールの趣旨に近い。
            # ここでは、どちらかが3回連続スタンドしたら、次の相手の判断を待たずに終了させるか、
            # あるいは、そのターンの両者の行動を見てから判断するか。
            # 今回は、シンプルにどちらかのスタンドカウントが3に達したら終了とする。
            if q_agent_stand_count >= 3 or omega_ai_stand_count >= 3:
                # 決着。Qエージェントの最後の状態・行動に対して最終報酬で学習。
                final_reward_val = compute_final_reward(calculate_total(q_hand), calculate_total(opponent_hand))
                reward_for_q_agent += final_reward_val # ここまでの報酬に加算
                agent.learn(last_q_agent_state, last_q_agent_action, reward_for_q_agent, None) # 終端状態
                game_terminated = True
                # print(f"Debug E{episode+1}-I{iteration}: Stand決着. R_Q={reward_for_q_agent}")
                agent.decay_epsilon() # エピソード終了
                continue # 次のエピソードへ

            # ----- ゲームが継続する場合のQ学習エージェントの学習 -----
            # Qエージェントの行動後、OmegaAIの行動があり、ゲームがまだ終了していない場合
            # Qエージェントの次の状態 s' を観測し、Q(s,a) を更新する。
            # 次の状態 s' は、OmegaAIの行動後の盤面。
            if last_q_agent_state and last_q_agent_action and not game_terminated:
                q_total_after_omega_turn = calculate_total(q_hand) # OmegaAIの行動でQの手札は変わらない
                opponent_up_card_after_omega_turn = opponent_hand[0] if opponent_hand else 0 # OmegaAIのヒットで変わりうる
                
                next_q_agent_state = agent.get_state(q_total_after_omega_turn, opponent_up_card_after_omega_turn, deck)
                agent.learn(last_q_agent_state, last_q_agent_action, reward_for_q_agent, next_q_agent_state)
                # print(f"Debug E{episode+1}-I{iteration}: QAgent step learn. R={reward_for_q_agent}, S={last_q_agent_state}, A={last_q_agent_action}, S'={next_q_agent_state}")

        # ループが最大反復回数に達して終了した場合 (通常はバーストかスタンドで終わるはず)
        if not game_terminated:
            # この場合も何らかの最終報酬で学習させるべき
            final_reward_val = compute_final_reward(calculate_total(q_hand), calculate_total(opponent_hand))
            reward_for_q_agent += final_reward_val
            agent.learn(last_q_agent_state, last_q_agent_action, reward_for_q_agent, None) # 終端状態として学習
            game_terminated = True # 明示的に終了
            # print(f"Debug E{episode+1}-I{iteration}: Max iteration. R_Q={reward_for_q_agent}")
            agent.decay_epsilon() # エピソード終了

        if (episode + 1) % 500 == 0:
            print(f"Phase1: {episode + 1}/{episodes} エピソード終了, ε: {agent.epsilon:.4f}")
            
    agent.save("q_table.json")


# --- 学習モード Phase2: Q学習 vs Q学習 ---
def simulate_q_vs_q(agent, episodes=2000000): # episodesは元の値に戻しました
    max_iterations = 50
    results = {"agent1_win": 0, "agent2_win": 0, "draw": 0}

    # 自己対戦では、同じエージェントインスタンス（同じQテーブル）を使って
    # Agent1とAgent2の役割を交互に演じさせることが一般的。
    # ここでは agent をそのまま使用します。

    for episode_num in range(episodes):
        deck = shuffle_deck()

        if len(deck) < 4: # 初期手札に最低4枚必要
            # print(f"エピソード {episode_num + 1} スキップ: デッキのカードが不足しています。")
            continue
        
        agent1_hand = [deck.pop(), deck.pop()]
        agent2_hand = [deck.pop(), deck.pop()]
        
        stand_count1 = 0
        stand_count2 = 0
        iteration = 0
        
        game_terminated = False

        # 各エージェントの直前の状態と行動を保持
        last_state1, last_action1 = None, None
        last_state2, last_action2 = None, None

        while iteration < max_iterations and not game_terminated:
            iteration += 1
            
            # ----- Agent1 のターン -----
            if not game_terminated:
                total1_before_action = calculate_total(agent1_hand)
                opponent_card_for_a1 = agent2_hand[0] if agent2_hand else 0
                state1 = agent.get_state(total1_before_action, opponent_card_for_a1, deck)
                action1 = agent.choose_action(state1, total1_before_action)

                last_state1, last_action1 = state1, action1 # 記録
                reward1 = 0

                if action1 == "hit":
                    stand_count1 = 0
                    if deck:
                        agent1_hand.append(deck.pop())
                        new_total1 = calculate_total(agent1_hand)
                        reward1 = compute_intermediate_reward(total1_before_action, new_total1)
                        if new_total1 > BURST_LIMIT:
                            reward1 += -10 # バーストペナルティ
                            results["agent2_win"] += 1
                            game_terminated = True
                            # Agent1のバーストで学習
                            agent.learn(state1, action1, reward1, None)
                            # Agent2は勝利なので、Agent2の最後の行動に報酬を与える (もしあれば)
                            if last_state2 and last_action2:
                                agent.learn(last_state2, last_action2, 1, None) # 暫定的な勝利報酬
                    else: # デッキ切れ
                        action1 = "stand" # スタンドとして扱う
                        last_action1 = "stand"
                        stand_count1 += 1
                else: # Agent1 スタンド
                    stand_count1 += 1
                
                # Agent2のターンに移る前に、Agent1の学習を行う (まだゲームが終了していない場合)
                # この学習は、Agent1の行動の結果と、Agent2の行動後の状態(next_state)を見て行われるべき
                # しかし、Agent2の行動はまだなので、ここではAgent1の行動による即時報酬のみを考慮し、
                # Agent2の行動後にnext_stateが決まったら再度学習する、という形にするか、
                # あるいは、ここでは学習せず、Agent2の行動後にまとめて学習する。
                # 今回は、Agent1の行動->Agent2の行動 という1サイクルで学習を試みる。
                # そのため、Agent1の学習はAgent2の行動後に行う。

            # ----- Agent2 のターン -----
            if not game_terminated:
                total2_before_action = calculate_total(agent2_hand)
                opponent_card_for_a2 = agent1_hand[0] if agent1_hand else 0
                state2 = agent.get_state(total2_before_action, opponent_card_for_a2, deck)
                action2 = agent.choose_action(state2, total2_before_action)

                last_state2, last_action2 = state2, action2 # 記録
                reward2 = 0

                if action2 == "hit":
                    stand_count2 = 0
                    if deck:
                        agent2_hand.append(deck.pop())
                        new_total2 = calculate_total(agent2_hand)
                        reward2 = compute_intermediate_reward(total2_before_action, new_total2)
                        if new_total2 > BURST_LIMIT:
                            reward2 += -10 # バーストペナルティ
                            results["agent1_win"] += 1
                            game_terminated = True
                            # Agent2のバーストで学習
                            agent.learn(state2, action2, reward2, None)
                            # Agent1は勝利なので、Agent1の最後の行動に報酬を与える
                            if last_state1 and last_action1: # last_state1, last_action1がNoneでないことを確認
                                agent.learn(last_state1, last_action1, 1, None) # 暫定的な勝利報酬
                    else: # デッキ切れ
                        action2 = "stand" # スタンドとして扱う
                        last_action2 = "stand"
                        stand_count2 += 1
                else: # Agent2 スタンド
                    stand_count2 += 1

                # ----- 1サイクルの終了、学習の実行 -----
                if not game_terminated:
                    # Agent1 の学習: Agent1の行動(s1,a1) -> Agent2の行動後の状態(next_s1)
                    if last_state1 and last_action1: # Agent1が行動していた場合
                        total1_after_a2 = calculate_total(agent1_hand)
                        opponent_card_for_a1_next = agent2_hand[0] if agent2_hand else 0
                        next_state1 = agent.get_state(total1_after_a2, opponent_card_for_a1_next, deck)
                        # reward1 は Agent1 の行動による即時報酬
                        agent.learn(last_state1, last_action1, reward1, next_state1)
                    
                    # Agent2 の学習: Agent2の行動(s2,a2) -> Agent1の次の行動前の状態(next_s2)
                    # 次のイテレーションの最初にAgent1の状態が確定するので、そこでnext_stateが決まる
                    # ここではAgent2の行動による即時報酬のみで学習し、next_stateは次のAgent1の状態
                    if last_state2 and last_action2: # Agent2が行動していた場合
                        total2_after_a1_next_turn = calculate_total(agent2_hand) # A2の手札はA1の次ターン開始時も同じ
                        opponent_card_for_a2_next = agent1_hand[0] if agent1_hand else 0 # A1の次ターン開始時のA1のカード
                        next_state2 = agent.get_state(total2_after_a1_next_turn, opponent_card_for_a2_next, deck)
                        # reward2 は Agent2 の行動による即時報酬
                        agent.learn(last_state2, last_action2, reward2, next_state2)


            # ----- 連続スタンドチェック -----
            if not game_terminated and (stand_count1 >= 3 or stand_count2 >= 3):
                game_terminated = True # ゲーム終了フラグを立てる
                # この時点で決着とする (勝敗判定はループ後)

        # ----- エピソード終了処理 (ループ後) -----
        # バーストではなく、スタンド等で終了した場合の最終的な勝敗判定と報酬
        if not (results["agent1_win"] > 0 and iteration < max_iterations and calculate_total(agent2_hand) > BURST_LIMIT) and \
           not (results["agent2_win"] > 0 and iteration < max_iterations and calculate_total(agent1_hand) > BURST_LIMIT):
            # 上記はバーストで既に結果が出ている場合を除外する意図だが、よりシンプルに
            # game_terminated が True になった原因がバースト以外の場合、とするのが良い
            
            final_total1 = calculate_total(agent1_hand)
            final_total2 = calculate_total(agent2_hand)
            
            outcome = 0 # 0: draw, 1: agent1 win, -1: agent2 win
            # バーストの再チェック (ループ内で処理済みのはずだが念のため)
            if final_total1 > BURST_LIMIT and final_total2 > BURST_LIMIT: outcome = 0
            elif final_total1 > BURST_LIMIT: outcome = -1
            elif final_total2 > BURST_LIMIT: outcome = 1
            else: # バーストなし
                outcome = judge(final_total1, final_total2)

            # 結果をresultsに記録 (バーストですでにカウントされていなければ)
            if outcome == 1 and not (calculate_total(agent2_hand) > BURST_LIMIT and iteration < max_iterations):
                 results["agent1_win"] += 1
            elif outcome == -1 and not (calculate_total(agent1_hand) > BURST_LIMIT and iteration < max_iterations):
                 results["agent2_win"] += 1
            elif outcome == 0 and not ((calculate_total(agent1_hand) > BURST_LIMIT or calculate_total(agent2_hand) > BURST_LIMIT) and iteration < max_iterations) :
                 results["draw"] += 1
            
            # 最終的な報酬で学習 (最後の状態行動ペアに対して)
            reward_agent1_final = 0
            reward_agent2_final = 0
            if outcome == 1: reward_agent1_final = 1; reward_agent2_final = -1
            elif outcome == -1: reward_agent1_final = -1; reward_agent2_final = 1
            
            if last_state1 and last_action1: # Agent1の最後の行動に最終報酬
                agent.learn(last_state1, last_action1, reward_agent1_final, None) # 終端なのでnext_stateはNone
            if last_state2 and last_action2: # Agent2の最後の行動に最終報酬
                agent.learn(last_state2, last_action2, reward_agent2_final, None) # 終端なのでnext_stateはNone

        agent.decay_epsilon()
        if (episode_num + 1) % 500 == 0:
            print(f"Phase2: {episode_num + 1}/{episodes} エピソード終了, ε: {agent.epsilon:.4f}, "
                  f"A1勝: {results['agent1_win']}, A2勝: {results['agent2_win']}, 引分: {results['draw']}")

    return results

# --- Q学習エージェントの初期化と読み込み ---
agent = QLearningAgent()
q_table_loaded = False # Qテーブルが正常に読み込まれたかのフラグ

try:
    # まず q_table2.json (Phase2の結果) を読み込もうと試みる
    agent.load("q_table2.json")
    print("INFO: q_table2.json を読み込みました。")
    q_table_loaded = True
except (FileNotFoundError, json.JSONDecodeError):
    print("INFO: q_table2.json が見つからないか壊れています。q_table.json を試みます。")
    try:
        # q_table2.json がなければ q_table.json (Phase1の結果) を読み込む
        agent.load("q_table.json")
        print("INFO: q_table.json を読み込みました。")
        q_table_loaded = True
    except (FileNotFoundError, json.JSONDecodeError):
        print("WARNING: q_table.json も見つからないか壊れています。新しいQテーブルで開始します。")
        # どちらのファイルもなければ、agent.q_table は空のまま (QLearningAgentの__init__で初期化されている)

if not q_table_loaded:
    print("INFO: 有効な学習済みQテーブルが見つからなかったため、空のQテーブルで開始します。")


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
        
    # --- ゲームカウンターの管理 (SPカード補充用) ---
    session['game_count'] = session.get('game_count', 0) + 1
    current_game_count = session['game_count']

    # --- SPカード配布（相手の命を減らすカードは毎回補充する） ---
    # プレイヤーへの配布
    if 'player_sp_cards' not in session: # 初回のみ辞書を初期化
        session['player_sp_cards'] = {}

    player_sp_cards = session['player_sp_cards'] # 直接辞書を操作する
    
# 定期的なSPカード補充 (sp_minus_3)
    card_id_to_give_regular = "sp_minus_3"
    if card_id_to_give_regular in SP_CARDS_MASTER:
       player_sp_cards[card_id_to_give_regular] = player_sp_cards.get(card_id_to_give_regular, 0) + 1
       print(f"DEBUG: Player given regular SP card: {card_id_to_give_regular}. New count: {player_sp_cards.get(card_id_to_give_regular)}") 
    else:
        print(f"警告: プレイヤーへの定期配布カードID '{card_id_to_give_regular}' がマスターに存在しません。")

    # --- 手札を戻すリターンSPカード専用 ---
    card_id_return = "sp_return_last_card"
    # (current_game_count % 5 == 0 or random.randint(1, 5) == 1) の条件が正しいか
    # 例えば、current_game_count が常に1でリセットされてしまっているなどないか。
    # random.randint(1, 5) == 1 は約20%の確率。
    gacha_success = False
    if current_game_count % 5 == 0:
        gacha_success = True
        print(f"DEBUG: Game count {current_game_count} is a multiple of 5.")
    if random.randint(1, 5) == 1:
        gacha_success = True
        print(f"DEBUG: Random gacha success for return card.")

    if gacha_success: # 修正: 条件をまとめて評価
        if card_id_return in SP_CARDS_MASTER:
            player_sp_cards[card_id_return] = player_sp_cards.get(card_id_return, 0) + 1
            print(f"DEBUG: Player given RARE SP card: {card_id_return}. New count: {player_sp_cards[card_id_return]} (Game count: {current_game_count})") # ★デバッグ追加★
        else:
            print(f"DEBUG: card_id_return '{card_id_return}' not in SP_CARDS_MASTER for player.") # ★デバッグ追加★
    else:
        print(f"DEBUG: No rare SP card for player this game (Game count: {current_game_count}).") # ★デバッグ追加★

    session['player_sp_cards'] = player_sp_cards # セッションに再格納
    print(f"DEBUG: Player SP cards in session after update: {session['player_sp_cards']}") # ★デバッグ追加★  

    # AIのSPカード
    if 'ai_sp_cards' not in session:
        session['ai_sp_cards'] = {}
    ai_sp_cards = session['ai_sp_cards']

    # AIへの定期補充 (card_id_to_give_regular を使用) 
    if card_id_to_give_regular in SP_CARDS_MASTER:
        ai_sp_cards[card_id_to_give_regular] = ai_sp_cards.get(card_id_to_give_regular, 0) + 1
        print(f"DEBUG: AI given regular SP card: {card_id_to_give_regular}. New count: {ai_sp_cards.get(card_id_to_give_regular)}")
    else:
        # このelseは card_id_to_give_regular がマスターにない場合なので、警告を出すならここ
        print(f"警告: AIへの定期配布カードID '{card_id_to_give_regular}' がマスターに存在しません。")


    # AIへの確率補充 (card_id_return を使用) 
    gacha_success_ai = False # AI用のガチャ成功フラグ
    if current_game_count % 5 == 0: gacha_success_ai = True
    if random.randint(1, 5) == 1: gacha_success_ai = True # 上と同様、orで繋ぐか検討

    if gacha_success_ai:
        if card_id_return in SP_CARDS_MASTER:
            ai_sp_cards[card_id_return] = ai_sp_cards.get(card_id_return, 0) + 1
            print(f"DEBUG: AI given RARE SP card: {card_id_return}. New count: {ai_sp_cards.get(card_id_return)} (Game count: {current_game_count})")
        else:
            # このelseは card_id_return がマスターにない場合
            print(f"警告: AIへの確率配布カードID '{card_id_return}' がマスターに存在しません。")
    else:
        print(f"DEBUG: No rare SP card for AI this game (Game count: {current_game_count}).")
    session['ai_sp_cards'] = ai_sp_cards
    # ここまでAIへのSPカード配布修正


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

    # --- ガード節1: プレイヤーのターンではない場合 ---
    if session.get("turn") != "player":
        # AIの手札を隠して「あなたのターンではありません」というメッセージと共に現在の状態を返す
        current_ai_hand = session.get("ai_hand", [])
        ai_hand_display = [0] + current_ai_hand[1:] if current_ai_hand else []
        
        print("INFO: Hit rejected, not player's turn.")
        return jsonify({
            "message": "Not your turn",
            "player_hand": session.get("player_hand", []),
            "ai_hand": ai_hand_display,
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            "game_over": session.get("turn") == "end" # ゲームが終了している可能性も考慮
        })

    # --- ガード節2: デッキが空の場合 ---
    if not session.get("deck"):
        print("ERROR: Hit failed, deck is empty.")
        return jsonify({
            "error": "No more cards in the deck.",
            "player_points": session.get('player_points', INITIAL_POINTS),
            "ai_points": session.get('ai_points', INITIAL_POINTS),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
        }), 400

    # --- メインのヒット処理 ---
    
    # プレイヤーがヒットしたことを記録
    session["player_consecutive_stands_for_ai_logic"] = 0 
    session['player_chose_stand_this_turn'] = False
    
    # デッキからカードを引いて手札に加える
    session["player_hand"].append(session["deck"].pop())
    
    # メッセージを組み立てる
    player_total = calculate_total(session["player_hand"])
    message = f"あなたがヒットしました。合計: {player_total}"

    # バーストした場合のみ、メッセージに追記
    if player_total > BURST_LIMIT:
        message += " (バースト！)"
        print(f"INFO: Player burst with total: {player_total}")
    
    # ターンをAIに移す (バースト有無に関わらず共通)
    session["turn"] = "ai"
    print(f"INFO: Turn changed to 'ai'.")

    # レスポンスを返す (バースト有無に関わらず共通)
    ai_hand_display = [0] + session["ai_hand"][1:] if session.get("ai_hand") else []
    return jsonify({
        "player_hand": session["player_hand"],
        "ai_hand": ai_hand_display,
        "player_points": session.get('player_points', INITIAL_POINTS),
        "ai_points": session.get('ai_points', INITIAL_POINTS),
        "player_sp_cards": session.get('player_sp_cards', {}),
        "ai_sp_cards": session.get('ai_sp_cards', {}),
        "declared_sp_card": session.get('declared_sp_card'),
        "ai_declared_sp_card": session.get('ai_declared_sp_card'),
        "game_over": False, # ヒット直後にゲームオーバーになることはない
        "message": message
    })


@app.route("/stand", methods=["POST"])
def stand():
    """プレイヤーがスタンド"""
    print(f"--- STAND request received. Current turn in session: {session.get('turn')}")
    if session.get("turn") == "player":
        session["player_consecutive_stands_for_ai_logic"] = session.get("player_consecutive_stands_for_ai_logic", 0) + 1 #プレイヤーの連続スタンド回数をインクリメント
        session['player_chose_stand_this_turn'] = True # このターンでプレイヤーがスタンドしたことを記録
        #session['both_consecutive_stands'] = 0 # プレイヤーが行動したので、AIとの連続スタンドは一旦リセットされるべきか、AIターンで判断するか。ここではAIターンで判断する前提
        
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

    # --- ガード節: AIのターンではない場合 ---
    if session.get("turn") != "ai":
        is_game_over = session.get("turn") == "end"
        ai_hand_to_return = session.get("ai_hand", [])
        if not is_game_over:
            ai_hand_to_return = [0] + ai_hand_to_return[1:] if ai_hand_to_return else []
        
        return jsonify({
            "message": "Not AI turn" if not is_game_over else "Game already over",
            "player_hand": session.get("player_hand", []),
            "ai_hand": ai_hand_to_return,
            "player_points": session.get('player_points'),
            "ai_points": session.get('ai_points'),
            "player_sp_cards": session.get('player_sp_cards', {}),
            "ai_sp_cards": session.get('ai_sp_cards', {}),
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            "game_over": is_game_over
        })

    # --- ターン開始時の準備 ---
    player_hand = session.get("player_hand", [])
    ai_hand = session.get("ai_hand", [])
    deck = session.get("deck", [])
    ai_sp_cards = session.get('ai_sp_cards', {}).copy()
    
    # --- 1. AIによる即時発動系SPカード「手札戻し」の使用判断 ---
    card_id_return = "sp_return_last_card"
    if ai_sp_cards.get(card_id_return, 0) > 0 and calculate_total(ai_hand) > BURST_LIMIT and len(ai_hand) > 2:
        print(f"INFO: AI is using INSTANT SP card: {card_id_return}")
        ai_sp_cards[card_id_return] -= 1
        returned_card = ai_hand.pop()
        deck.append(returned_card)
        random.shuffle(deck)
        
        card_name_return = SP_CARDS_MASTER.get(card_id_return, {}).get('name', card_id_return)
        message = f"AIは '{card_name_return}' を使用！ 最後に引いたカード ({returned_card}) を山札に戻しました。あなたのターンです。"
        
        session['ai_sp_cards'] = ai_sp_cards
        session["deck"] = deck
        session["ai_hand"] = ai_hand
        session["turn"] = "player"

        ai_hand_display = [0] + session["ai_hand"][1:] if session.get("ai_hand") else []
        return jsonify({
            "message": message,
            "player_hand": player_hand,
            "ai_hand": ai_hand_display,
            "player_points": session.get('player_points'),
            "ai_points": session.get('ai_points'),
            "player_sp_cards": session.get('player_sp_cards'),
            "ai_sp_cards": session.get('ai_sp_cards'),
            "declared_sp_card": session.get('declared_sp_card'),
            "ai_declared_sp_card": session.get('ai_declared_sp_card'),
            "game_over": False
        })
    
    # --- 2. AIによる宣言系SPカードの使用判断 ---
    sp_declare_message = ""
    ai_total = calculate_total(ai_hand)
    if not session.get('declared_sp_card') and not session.get('ai_declared_sp_card'):
        card_id_declare_type = "sp_minus_3"
        player_open_card = player_hand[0] if player_hand else 0
        if ai_total >= 18 and player_open_card <= 7 and ai_sp_cards.get(card_id_declare_type, 0) > 0:
            ai_sp_cards[card_id_declare_type] -= 1
            session['ai_declared_sp_card'] = card_id_declare_type
            card_name_declare = SP_CARDS_MASTER.get(card_id_declare_type, {}).get('name', card_id_declare_type)
            sp_declare_message = f"\nAIは '{card_name_declare}' の使用を宣言しました！"
            print(f"INFO: AI declared '{card_name_declare}'.")
            session['ai_sp_cards'] = ai_sp_cards # 消費したのでセッションを更新

    # --- 3. AIのヒット/スタンド行動選択 ---
    player_total = calculate_total(player_hand)
    player_consecutive_stands = session.get("player_consecutive_stands_for_ai_logic", 0)
    if ai_total > player_total and player_consecutive_stands >= 2:
        action_by_ai = "stand"
        print(f"INFO: AI forced to stand by player牽制rule.")
    else:
        player_open_card_for_q = player_hand[0] if player_hand else 0
        state_for_q_agent = agent.get_state(ai_total, player_open_card_for_q, deck)
        action_by_ai = agent.choose_action(state_for_q_agent, ai_total, is_training=False)

    # --- 4. AIの行動実行と、それに伴う状態遷移 ---
    action_message = ""
    is_game_over = False

    if action_by_ai == "hit":
        session["both_consecutive_stands"] = 0
        if not deck:
            action_message = "AI: ヒット。しかしデッキにカードがありませんでした。"
        else:
            session["ai_hand"].append(deck.pop())
            new_ai_total = calculate_total(session["ai_hand"])
            action_message = "AI: ヒット。"
            if new_ai_total > BURST_LIMIT:
                action_message += " (バースト！)"
                print(f"INFO: AI burst with total: {new_ai_total}")
        session["turn"] = "player"

    else: # action_by_ai == "stand"
        action_message = "AI: スタンド。"
        player_stood_last_turn = session.get('player_chose_stand_this_turn', False)
        if player_stood_last_turn:
            session["both_consecutive_stands"] = session.get("both_consecutive_stands", 0) + 1
        else:
            session["both_consecutive_stands"] = 0
        session['player_chose_stand_this_turn'] = False
        
        # 決着判定
        if session.get("both_consecutive_stands", 0) >= 3:
            print(f"INFO: Game ends, both stood 3 consecutive times.")
            # 新しい決着処理関数を呼び出す
            action_message = _finalize_round() # ここでメッセージが上書きされる
            is_game_over = True
        else:
            session["turn"] = "player"

    # --- 5. レスポンスの組み立て ---
    final_message = action_message + sp_declare_message
    if not is_game_over:
        final_message += " あなたのターンです。"

    ai_hand_to_return = session.get("ai_hand", [])
    if not is_game_over:
        ai_hand_to_return = [0] + ai_hand_to_return[1:] if ai_hand_to_return else []

    session.modified = True
    return jsonify({
        "message": final_message.strip(),
        "player_hand": player_hand,
        "ai_hand": ai_hand_to_return,
        "player_points": session.get('player_points'),
        "ai_points": session.get('ai_points'),
        "player_sp_cards": session.get('player_sp_cards'),
        "ai_sp_cards": session.get('ai_sp_cards'),
        "declared_sp_card": session.get('declared_sp_card'),
        "ai_declared_sp_card": session.get('ai_declared_sp_card'),
        "game_over": is_game_over
    })


@app.route('/use_sp_card', methods=['POST'])
def use_sp_card():
    """プレイヤーがSPカードを使用または宣言し、消費する"""
    print(f"--- USE_SP_CARD request received. Current turn: {session.get('turn')}")

    if session.get("turn") != "player":
        return jsonify({"error": "あなたのターンではありません。"}), 400

    data = request.get_json()
    card_id = data.get('card_id')

    if not card_id or card_id not in SP_CARDS_MASTER:
        return jsonify({"error": "無効なSPカードIDです。"}), 400

    card_info = SP_CARDS_MASTER[card_id]
    card_name = card_info.get('name', card_id)

    player_sp_cards = session.get('player_sp_cards', {})
    if player_sp_cards.get(card_id, 0) <= 0:
        return jsonify({"error": f"'{card_name}' を持っていません。"}), 400

    message = ""
    additional_data = {} # フロントに返す追加情報用（手札更新フラグなど）
    current_declared_card_player = session.get('declared_sp_card')
    current_declared_card_ai = session.get('ai_declared_sp_card')

    # --- SPカードの種類によって処理を分岐 ---
    is_instant_effect_card = card_info.get("effect_type") == "return_last_card" # 他の即時発動系もここに追加可能

    if is_instant_effect_card:
        # 即時発動系カードの場合 (例: 手札戻し)
        # このタイプのカードは、相手が宣言系カードを宣言中でも使用可能とする
        # (ただし、自分のターンであることは上記の session.get("turn") != "player" でチェック済み)

        # カード消費 (即時発動なので、効果処理が成功したら消費する方が良い場合もあるが、ここでは先に消費)
        player_sp_cards[card_id] -= 1
        session['player_sp_cards'] = player_sp_cards
        print(f"Player consumed INSTANT SP card: {card_id}.")

        if card_id == "sp_return_last_card":
            player_hand = session.get("player_hand", [])
            # 最初の2枚は戻せない、または手札が1枚以下は戻せないなど、ルールの明確化が必要
            # ここでは「手札が2枚より多い場合」に戻せるとする (初期手札2枚 + 1枚以上引いている)
            if len(player_hand) > 2: 
                returned_card = player_hand.pop()
                session.setdefault("deck", []).append(returned_card) # deckキーがなくてもエラーにならないように
                random.shuffle(session["deck"])
                session["player_hand"] = player_hand
                
                message = f"あなたが '{card_name}' を使用！ 最後に引いたカード ({returned_card}) を山札に戻しました。"
                message += f" 現在の手札合計: {calculate_total(player_hand)}"
                additional_data["player_hand_updated"] = True
                print(f"Player used '{card_name}', returned {returned_card}. New hand total: {calculate_total(player_hand)}")
            else:
                message = f"'{card_name}' を使用しようとしましたが、戻せる手札がありません（最低3枚必要）。カードは消費されました。"
                # カード消費のタイミングを再考する余地あり (効果不発なら消費しないなど)
                print(f"Player tried to use '{card_name}' but no card to return.")
        else:
            # 他の即時発動系カードの処理 (将来的に追加する場合)
            message = f"'{card_name}' を使用しましたが、この即時効果の処理が未実装です。"
        
        session["turn"] = "player" # 即時発動後もプレイヤーのターンが継続

    else: # 宣言系SPカードの場合 (従来のポイント操作系など)
        if current_declared_card_player:
            return jsonify({"error": "既にSPカードを使用宣言済みです。"}), 400
        if current_declared_card_ai:
            return jsonify({"error": "AIが既にSPカードを宣言中です（このSPカードは同時宣言できません）。"}), 400

        # カード消費
        player_sp_cards[card_id] -= 1
        session['player_sp_cards'] = player_sp_cards
        print(f"Player consumed DECLARE SP card: {card_id}.")

        # 宣言記録
        session['declared_sp_card'] = card_id
        print(f"Player declared SP card: {card_id}")
        message = f"あなたが '{card_name}' の使用を宣言しました。今回の勝負に勝てば効果が発動します。（カード消費済み）"
        session["turn"] = "player" # 宣言後もプレイヤーのターンが継続

    session.modified = True # セッションの変更を確実に保存

    # レスポンスに必要なデータを準備
    try:
        # ゲーム継続中はAIの最初のカードを隠す (表示用)
        ai_hand_display = [0] + session["ai_hand"][1:] if session.get("ai_hand") and len(session["ai_hand"]) >= 1 else session.get("ai_hand", [])
    except Exception as e:
        print(f"Error creating ai_hand_display in use_sp_card: {e}")
        ai_hand_display = session.get("ai_hand", [])


    response_data = {
        "message": message,
        "player_points": session.get('player_points', INITIAL_POINTS),
        "ai_points": session.get('ai_points', INITIAL_POINTS),
        "player_sp_cards": session['player_sp_cards'], # 更新されたプレイヤーのSPカード
        "declared_sp_card": session.get('declared_sp_card'), # 宣言中のプレイヤーのカード (あれば)
        "ai_sp_cards": session.get('ai_sp_cards', {}),
        "ai_declared_sp_card": session.get('ai_declared_sp_card'), # AIの宣言中カード
        "game_over": False, # SPカード使用では通常ゲームオーバーにはならない
        "player_hand": session.get("player_hand", []), # 「手札戻し」の場合、更新されている可能性あり
        "ai_hand": ai_hand_display # AIの手札 (表示用)
    }
    response_data.update(additional_data) # player_hand_updated などのフラグを追加

    return jsonify(response_data)


@app.route("/train", methods=["POST"])
def train_route():
    """Phase1 学習モード実行"""
    train_phase1(agent)
    return jsonify({"message": "Phase1 学習完了 (q_table.json 生成)"})

@app.route("/train2", methods=["POST"])
def train2_route():
    """Phase2 学習モード実行"""
    simulation_results = simulate_q_vs_q(agent, episodes=2000000)
    agent.save("q_table2.json")
    return jsonify({
        "message": "Phase2 学習完了 (q_table2.json 生成)",
        "simulation_results": simulation_results
    })


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


# 最後
if __name__ == "__main__":
    app.run(debug=True)
