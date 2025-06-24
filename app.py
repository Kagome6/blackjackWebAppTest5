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
        action = agent.choose_action(state, ai_total, is_training=False) 
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
    simulation_results = simulate_q_vs_q(agent, episodes=2000000)
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


# 最後
if __name__ == "__main__":
    app.run(debug=True)
