// DOM要素の取得
// ↓↓↓コメントアウト ↓↓↓
// const modeSelectionDiv = document.getElementById("mode-selection");
// const learnButton = document.getElementById("learn-button");
// const learn2Button = document.getElementById("learn2-button");
const playButton = document.getElementById("play-button");
const gameContainerDiv = document.getElementById("game-container");
const playerHandDiv = document.getElementById("player-hand");
const aiHandDiv = document.getElementById("ai-hand");
const hitButton = document.getElementById("hit-button");
const standButton = document.getElementById("stand-button");
const endGameDiv = document.getElementById("end-game");
const nextGameButton = document.getElementById("next-game-button");
const messageLogDiv = document.getElementById("message-log");
const playerPointsSpan = document.getElementById("player-points");
const aiPointsSpan = document.getElementById("ai-points");
const spCardListDiv = document.getElementById("sp-card-list");
const declaredCardNameSpan = document.getElementById("declared-card-name");
const aiSpCardListSpan = document.getElementById("ai-sp-card-list");
const aiDeclaredCardNameSpan = document.getElementById("ai-declared-card-name");
const resetAllButton = document.getElementById("reset-all-button");


// メッセージログに新しいメッセージを追加する関数
function appendMessage(msg) {
    const p = document.createElement("p");
    p.textContent = msg;
    messageLogDiv.appendChild(p);
    messageLogDiv.scrollTop = messageLogDiv.scrollHeight;
}

// カードの表示更新
function updateCards(playerHand, aiHand) {
    playerHandDiv.innerHTML = "";
    aiHandDiv.innerHTML = "";
    playerHand.forEach(card => {
        const cardDiv = document.createElement("div");
        cardDiv.classList.add("card");
        cardDiv.style.backgroundImage = `url('/static/images/card_${card}.png')`;
        playerHandDiv.appendChild(cardDiv);
    });
    // AIの手札表示
    aiHand.forEach(card => {
        const cardDiv = document.createElement("div");
        cardDiv.classList.add("card");
        let imageUrl;
        // カード番号に応じて画像URLを切り替え
        if (card === 0) { // Pythonから送られてきた特別な値 0 の場合
            imageUrl = `url('/static/images/card_unknown.png')`; // 「？」画像
        } else {
            imageUrl = `url('/static/images/card_${card}.png')`; // 通常のカード画像
        }
        // ここまで
        cardDiv.style.backgroundImage = imageUrl;
        aiHandDiv.appendChild(cardDiv);
    });
}

// ポイント表示更新
function updatePointsDisplay(playerPoints, aiPoints) {
    let playerPts = '--'; // ポイントを数値で保持するための変数
    let aiPts = '--';   // ポイントを数値で保持するための変数

    // サーバーから送られてきた値が有効なら表示を更新し、数値も保持
    if (playerPoints !== undefined && playerPoints !== null) {
        playerPts = playerPoints; // ポイントを数値で保持
        playerPointsSpan.textContent = playerPts;
    }
    if (aiPoints !== undefined && aiPoints !== null) {
        aiPts = aiPoints; // ポイントを数値で保持
        aiPointsSpan.textContent = aiPts;
    }

    // --- ↓↓↓ ゲームオーバー時の「次のゲームへ」ボタン制御を追加 ↓↓↓ ---
    // nextGameButton が取得できているか確認
    if (typeof nextGameButton !== 'undefined') {
        // endGameDiv が表示されている（＝ラウンド終了）場合のみ評価
        if (endGameDiv.style.display === "block") {
            // プレイヤーかAIのポイントが0以下かチェック
            if ((typeof playerPts === 'number' && playerPts <= 0) || (typeof aiPts === 'number' && aiPts <= 0)) {
                // ポイントが0以下なら無効化
                nextGameButton.disabled = true;
                // メッセージは毎回表示すると冗長なので、初回のみ表示するか検討
                // if (!document.getElementById('game-over-final-message')) { // 例: IDで管理
                //    const p = document.createElement('p');
                //    p.id = 'game-over-final-message';
                //    p.textContent = "ポイントが0になったため、次のゲームへは進めません。...";
                //    messageLogDiv.appendChild(p);
                // }
            } else {
                // ポイントが残っていれば有効化
                nextGameButton.disabled = false;
            }
        } else {
             // ゲーム中は無効
             nextGameButton.disabled = true;
        }
    }
    // --- ↑↑↑ ゲームオーバー時の「次のゲームへ」ボタン制御を追加 ↑↑↑ ---
}

      
/**
 * SPカードの表示を更新する関数
 * @param {Object} spCards - プレイヤーの所持SPカード情報
 * @param {string|null} declaredCardId - 現在宣言中のカードID (なければ null or undefined)
 */
function updateSpCardsDisplay(spCards, declaredCardId) { // ★ 引数に declaredCardId を追加 ★
    spCardListDiv.innerHTML = ''; // 表示クリア

    // --- 宣言中カード表示の更新を追加 ---
    if (declaredCardId && SP_CARDS_MASTER_JS && SP_CARDS_MASTER_JS[declaredCardId]) {
        // ★ SP_CARDS_MASTER_JS が必要 (後述) ★
        declaredCardNameSpan.textContent = SP_CARDS_MASTER_JS[declaredCardId].name || declaredCardId;
    } else if (declaredCardId) {
        declaredCardNameSpan.textContent = declaredCardId; // マスター情報なければID表示
    }
     else {
        declaredCardNameSpan.textContent = 'なし';
    }
    // --- 宣言中カード表示の更新を追加 ---


    if (!spCards || Object.keys(spCards).length === 0) {
        spCardListDiv.innerHTML = '<p>なし</p>';
        return;
    }

    for (const cardId in spCards) {
        const count = spCards[cardId];
        if (count > 0) {
            const cardInfoDiv = document.createElement('div');
            cardInfoDiv.classList.add('sp-card-item');

            // ★ カード名表示部分もマスター情報を使うようにする (後述) ★
            const cardName = (SP_CARDS_MASTER_JS && SP_CARDS_MASTER_JS[cardId]) ? SP_CARDS_MASTER_JS[cardId].name : cardId;
            const cardCountText = ` x ${count}`;

            const cardTextSpan = document.createElement('span');
            cardTextSpan.textContent = `${cardName}${cardCountText} `;
            cardInfoDiv.appendChild(cardTextSpan);

            const useButton = document.createElement('button');
            useButton.textContent = '使用宣言'; // ★ ボタンテキスト変更 ★
            useButton.classList.add('use-sp-button');
            useButton.dataset.cardId = cardId;

            // ★ ボタンの有効/無効状態を設定 (修正) ★
            // 1. 既に何か宣言中(declaredCardIdが存在する)なら無効
            // 2. 相手ターンなど操作不可状態(hitButtonが無効)なら無効
            // 3. このカードの枚数が0以下なら無効 (これはループ条件でカバーされているが一応)
            const isAlreadyDeclared = !!declaredCardId;
            const isNotPlayerTurn = hitButton.disabled; // ヒットボタンが無効ならプレイヤーのターンではない

            useButton.disabled = isAlreadyDeclared || isNotPlayerTurn;

            useButton.addEventListener('click', handleUseSpCard);
            cardInfoDiv.appendChild(useButton);

            spCardListDiv.appendChild(cardInfoDiv);
        }
    }

    if (spCardListDiv.innerHTML === '') {
         spCardListDiv.innerHTML = '<p>なし</p>';
    }
}

/**
 * AIのSPカード表示を更新する関数 (簡易版 - 名前と枚数のみ)
 * @param {Object} aiSpCards - AIの所持SPカード情報
 */
function updateAISpCardsDisplay(aiSpCards) {
    let displayText = "なし";
    if (aiSpCards && Object.keys(aiSpCards).length > 0) {
        const cardEntries = [];
        for (const cardId in aiSpCards) {
            const count = aiSpCards[cardId];
            if (count > 0) {
                const cardName = (SP_CARDS_MASTER_JS && SP_CARDS_MASTER_JS[cardId]) ? SP_CARDS_MASTER_JS[cardId].name : cardId;
                cardEntries.push(`${cardName} x ${count}`);
            }
        }
        if (cardEntries.length > 0) {
            displayText = cardEntries.join(', '); // カンマ区切りで表示
        }
    }
    aiSpCardListSpan.textContent = displayText;
}

/**
 * AIの宣言中カード表示を更新する関数
 * @param {string|null} declaredCardId - AIが宣言中のカードID
 */
function updateAIDeclaredCardDisplay(declaredCardId) {
    if (declaredCardId && SP_CARDS_MASTER_JS && SP_CARDS_MASTER_JS[declaredCardId]) {
        aiDeclaredCardNameSpan.textContent = SP_CARDS_MASTER_JS[declaredCardId].name || declaredCardId;
    } else if (declaredCardId) {
        aiDeclaredCardNameSpan.textContent = declaredCardId;
    } else {
        aiDeclaredCardNameSpan.textContent = 'なし';
    }
}

// --- ★ SPカードのマスター情報をJSでも保持する ★ ---
// 本来はサーバーから取得するのが望ましいが、一旦ここで定義
const SP_CARDS_MASTER_JS = {
    "sp_minus_3": { "name": "ポイント-3", "description": "相手のポイントを3減らす" }
    // Python側の SP_CARDS_MASTER と内容を合わせておく
};
// -------------------------------------------------


/**
 * SPカード使用宣言ボタンがクリックされたときの処理
 * @param {Event} event - クリックイベント
 */
async function handleUseSpCard(event) {
    const button = event.target;
    const cardId = button.dataset.cardId;

    // --- ボタン無効化 (API呼び出し前) ---
    button.disabled = true; // クリックされたボタン自身
    hitButton.disabled = true;
    standButton.disabled = true;
    // 他のSPカードボタンも全て無効化
    document.querySelectorAll('.use-sp-button').forEach(btn => btn.disabled = true);

    const cardName = (SP_CARDS_MASTER_JS && SP_CARDS_MASTER_JS[cardId]) ? SP_CARDS_MASTER_JS[cardId].name : cardId;
    appendMessage(`'${cardName}' の使用を宣言します...`);

    try {
        const response = await fetch('/use_sp_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', },
            body: JSON.stringify({ card_id: cardId }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `サーバーエラー: ${response.status}`);
        }

        // --- ↓↓↓ 修正箇所: ボタン状態の更新を先に行う ↓↓↓ ---
        // SPカード宣言後はプレイヤーのターンが続くのでヒット/スタンドを有効化
        hitButton.disabled = false;
        standButton.disabled = false;
        // SPカードボタンの状態は、この後呼び出す updateSpCardsDisplay で
        // data.declared_sp_card を見て適切に設定される
        // (宣言されたので、全てのSPカードボタンは disabled = true になるはず)
        // --- ↑↑↑ 修正箇所: ボタン状態の更新を先に行う ↑↑↑ ---

        // --- 表示更新 (ボタン状態が確定した後) ---
        updatePointsDisplay(data.player_points, data.ai_points);
        // プレイヤーのSPカード表示更新 (宣言中カードIDも渡す)
        updateSpCardsDisplay(data.player_sp_cards, data.declared_sp_card || null); // || null を追加
        // AIのSPカード表示更新
        updateAISpCardsDisplay(data.ai_sp_cards);
        // AIの宣言中カード表示更新
        updateAIDeclaredCardDisplay(data.ai_declared_sp_card || null);
        // 手札表示は宣言では変わらないので不要
        // updateCards(data.player_hand, data.ai_hand);
        appendMessage(data.message); // サーバーからのメッセージを表示

    } catch (error) {
        console.error("Error declaring SP card:", error);
        appendMessage(`SPカード宣言エラー: ${error.message}`);
        // エラー時は操作可能に戻す
        hitButton.disabled = false;
        standButton.disabled = false;
        // エラーが発生した場合、SPカードボタンの状態をどうするか？
        // → 宣言前の状態に戻すのが自然か。サーバーから最新情報を再取得して
        //   updateSpCardsDisplay を呼び出すのが理想だが、暫定的に
        //   エラー発生前のSPカード情報で再度 updateSpCardsDisplay を呼ぶなど。
        //   あるいは、単純に全てのSPボタンを有効に戻す（枚数表示と矛盾する可能性あり）
         document.querySelectorAll('.use-sp-button').forEach(btn => btn.disabled = false); // 一旦有効に戻す

    }
}


// AIターン呼び出し
async function aiTurn() {
    try {
        const response = await fetch("/ai_turn", { method: "POST" });
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json(); // レスポンスを受け取る

        // --- ↓↓↓ 修正箇所: ボタン状態の更新を先に行う ↓↓↓ ---
        let isGameOver = data.game_over || false; // game_over フラグを取得

        if (!isGameOver) {
             // ゲームが続くならプレイヤーのターンなのでボタンを有効化
             hitButton.disabled = false;
             standButton.disabled = false;
        } else {
             // ゲームオーバーならボタンを無効化
             hitButton.disabled = true;
             standButton.disabled = true;
             endGameDiv.style.display = "block"; // ゲーム終了表示 (「次のゲームへ」ボタン表示)
        }
        // --- ↑↑↑ 修正箇所: ボタン状態の更新を先に行う ↑↑↑ ---

        // --- 表示更新関数呼び出し (ボタン状態が確定した後) ---
        updatePointsDisplay(data.player_points, data.ai_points);
        // プレイヤーのSPカード表示更新 (宣言中カードIDも渡す)
        updateSpCardsDisplay(data.player_sp_cards, data.declared_sp_card || null);
        // AIのSPカード表示更新
        updateAISpCardsDisplay(data.ai_sp_cards);
        // AIの宣言中カード表示更新
        updateAIDeclaredCardDisplay(data.ai_declared_sp_card || null);
        // 手札表示更新
        updateCards(data.player_hand, data.ai_hand);

        appendMessage(data.message || ""); // メッセージ追加

        // ゲームオーバー時の追加処理 (ポイント0チェックと「次のゲームへ」ボタンの状態更新)
        if (isGameOver) {
             // updatePointsDisplay を再度呼び出して「次のゲームへ」ボタンの状態を再評価
             updatePointsDisplay(data.player_points, data.ai_points);
        }

    } catch (error) {
        console.error("Error in AI turn:", error);
        appendMessage("AIの動作中にエラーが発生しました。");
        // エラー時も操作可能に戻す
        hitButton.disabled = false;
        standButton.disabled = false;
        // エラー時に他の表示も更新すべきか検討 (例: SPカードボタンの状態など)
        // updateSpCardsDisplay(...) など
    }
}

// ゲーム開始
async function startGame() {
    try {
        const response = await fetch("/start_game", { method: "POST" });
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();

        // --- ↓↓↓ ★★★ ボタン状態の初期化を先に実行 ★★★ ↓↓↓ ---
        // ゲーム開始時はヒット/スタンド有効
        hitButton.disabled = false;
        standButton.disabled = false;
        // 「次のゲームへ」ボタンは隠す & 無効化
        endGameDiv.style.display = "none";
        // nextGameButton の取得が必要 (もし未取得ならファイル上部で取得)
        if (typeof nextGameButton !== 'undefined') { // nextGameButton が定義されていれば
             nextGameButton.disabled = true;
        }
        // --- ↑↑↑ ★★★ ボタン状態の初期化を先に実行 ★★★ ↑↑↑ ---

        // --- 表示更新 (ボタン状態が確定した後) ---
        updatePointsDisplay(data.player_points, data.ai_points);
        // プレイヤーSPカード表示 (宣言状態も渡す - 開始時はnullのはず)
        updateSpCardsDisplay(data.player_sp_cards, data.declared_sp_card || null);
        // AI SPカード表示
        updateAISpCardsDisplay(data.ai_sp_cards);
        // AI 宣言状態表示 (開始時はnullのはず)
        updateAIDeclaredCardDisplay(data.ai_declared_sp_card || null);
        // 手札表示
        updateCards(data.player_hand, data.ai_hand);

        // メッセージログクリアと初期メッセージ表示
        messageLogDiv.innerHTML = "";
        appendMessage(data.load_status || "");
        appendMessage(data.message || "ゲーム開始！");

    } catch (error) {
        console.error("Error starting game:", error);
        appendMessage("ゲーム開始時にエラーが発生しました。");
        // エラー時は操作可能に戻す
        hitButton.disabled = false;
        standButton.disabled = false;
        // エラー時に nextGameButton も無効にしておくなど検討
        // if (typeof nextGameButton !== 'undefined') nextGameButton.disabled = true;
    }
}

// ヒットボタン
hitButton.addEventListener("click", async () => {
    // --- ボタン無効化 (API呼び出し前) ---
    hitButton.disabled = true;
    standButton.disabled = true;
    // SPカードボタンも一時的に無効化する方が安全
    document.querySelectorAll('.use-sp-button').forEach(btn => btn.disabled = true);

    try {
        const response = await fetch("/hit", { method: "POST" });
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();

        // --- ↓↓↓ 修正箇所: ボタン状態の更新を先に行う ↓↓↓ ---
        let isGameOver = data.game_over || false;
        if (isGameOver) {
             // ゲームオーバーならボタンは無効のまま
             endGameDiv.style.display = "block"; // ゲーム終了表示
        } else {
             // ヒット後はAIターンなので、ヒット/スタンドボタンは無効のまま
             // (SPカードボタンの状態は updateSpCardsDisplay で決定される)
             hitButton.disabled = true; // 念のため再設定
             standButton.disabled = true; // 念のため再設定
        }
        // --- ↑↑↑ 修正箇所: ボタン状態の更新を先に行う ↑↑↑ ---

        // --- 表示更新 (ボタン状態が確定した後) ---
        updatePointsDisplay(data.player_points, data.ai_points);
        // プレイヤーのSPカード表示更新 (宣言中カードIDも渡す)
        updateSpCardsDisplay(data.player_sp_cards, data.declared_sp_card || null);
        // AIのSPカード表示更新
        updateAISpCardsDisplay(data.ai_sp_cards);
        // AIの宣言中カード表示更新
        updateAIDeclaredCardDisplay(data.ai_declared_sp_card || null);
        // 手札表示更新
        updateCards(data.player_hand, data.ai_hand);
        appendMessage(data.message || ""); // メッセージ追加

        // --- 次のアクション ---
        if (isGameOver) {
            // ゲームオーバー時の追加処理 (ポイント0チェックと「次のゲームへ」ボタンの状態更新)
            updatePointsDisplay(data.player_points, data.ai_points);
        } else {
            // AIターンを呼ぶ前に少し待つ場合 (任意)
            // await new Promise(resolve => setTimeout(resolve, 500));
            await aiTurn(); // AIターンへ
        }
    } catch (error) {
        console.error("Error in hit:", error);
        appendMessage("ヒット処理中にエラーが発生しました。");
        // エラー時は操作可能に戻す
        hitButton.disabled = false;
        standButton.disabled = false;
        // エラー時にSPカードボタンも有効に戻す (updateSpCardsDisplay を呼ぶなどして再評価)
        // サーバーから最新状態を取得して再表示するのが理想
        // updateSpCardsDisplay(...)
    }
});

// スタンドボタン
standButton.addEventListener("click", async () => {
    // --- ボタン無効化 (API呼び出し前) ---
    hitButton.disabled = true;
    standButton.disabled = true;
    // SPカードボタンも一時的に無効化する方が安全
    document.querySelectorAll('.use-sp-button').forEach(btn => btn.disabled = true);

    try {
        const response = await fetch("/stand", { method: "POST" });
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();

        // --- ↓↓↓ 修正箇所: ボタン状態の更新を先に行う ↓↓↓ ---
        // スタンド直後は通常 isGameOver = false のはずだが、念のためチェック
        let isGameOver = data.game_over || false;
         if (isGameOver) {
              hitButton.disabled = true;
              standButton.disabled = true;
              endGameDiv.style.display = "block"; // ゲーム終了表示
         } else {
              // スタンド後はAIターンなので、ヒット/スタンドボタンは無効のまま
              hitButton.disabled = true; // 念のため再設定
              standButton.disabled = true; // 念のため再設定
         }
        // --- ↑↑↑ 修正箇所: ボタン状態の更新を先に行う ↑↑↑ ---

        // --- 表示更新 (ボタン状態が確定した後) ---
        updatePointsDisplay(data.player_points, data.ai_points);
        // プレイヤーのSPカード表示更新 (宣言中カードIDも渡す)
        updateSpCardsDisplay(data.player_sp_cards, data.declared_sp_card || null);
        // AIのSPカード表示更新
        updateAISpCardsDisplay(data.ai_sp_cards);
        // AIの宣言中カード表示更新
        updateAIDeclaredCardDisplay(data.ai_declared_sp_card || null);
        // 手札表示更新 (スタンド時は変わらないが表示してもOK)
        updateCards(data.player_hand, data.ai_hand);
        appendMessage(data.message || ""); // メッセージ追加

        // --- 次のアクション ---
        if (isGameOver) {
            // ゲームオーバー時の追加処理 (ポイント0チェックと「次のゲームへ」ボタンの状態更新)
            updatePointsDisplay(data.player_points, data.ai_points);
        } else {
            // AIターンを呼ぶ前に少し待つ場合 (任意)
            // await new Promise(resolve => setTimeout(resolve, 500));
            await aiTurn(); // AIターンへ
        }
    } catch (error) {
        console.error("Error in stand:", error);
        appendMessage("スタンド処理中にエラーが発生しました。");
        // エラー時は操作可能に戻す
        hitButton.disabled = false;
        standButton.disabled = false;
        // エラー時にSPカードボタンも有効に戻す (updateSpCardsDisplay を呼ぶなどして再評価)
        // updateSpCardsDisplay(...)
    }
});

// --- イベントリスナーの設定 ---
// ここはメンテナンス実行時以外はコメントアウト

// Phase1 学習ボタン
//if (learnButton) { // learnButton要素が存在する場合のみリスナーを設定
//    learnButton.addEventListener("click", async () => {
//        appendMessage("Phase1 学習を開始します... (時間がかかる場合があります)");
//        learnButton.disabled = true; // 学習中はボタンを無効化
//        learn2Button.disabled = true; // 他の学習ボタンも無効化
//        playButton.disabled = true;   // プレイボタンも無効化
//
//        try {
//            const response = await fetch("/train", { method: "POST" });
//            if (!response.ok) {
//                const errorData = await response.json().catch(() => ({ message: "サーバーからの応答が不正です。" }));
//                throw new Error(errorData.message || `学習サーバーエラー: ${response.status}`);
//            }
//            const data = await response.json();
//            appendMessage(data.message || "Phase1 学習が完了しました。");
//        } catch (error) {
//            console.error("Error in Phase1 training:", error);
//            appendMessage(`Phase1 学習エラー: ${error.message}`);
//        } finally {
//            learnButton.disabled = false; // 学習終了後（成功・失敗問わず）ボタンを有効化
//            learn2Button.disabled = false;
//           playButton.disabled = false;
//        }
//    });
//} else {
    console.warn("learn-button がHTML内に見つかりません。");
//}
//
// Phase2 学習ボタン
//if (learn2Button) { // learn2Button要素が存在する場合のみリスナーを設定
//    learn2Button.addEventListener("click", async () => {
//        appendMessage("Phase2 学習を開始します... (非常に時間がかかる場合があります)");
//        learnButton.disabled = true;
//        learn2Button.disabled = true;
//        playButton.disabled = true;
//
//        try {
//           const response = await fetch("/train2", { method: "POST" });
//            if (!response.ok) {
//                const errorData = await response.json().catch(() => ({ message: "サーバーからの応答が不正です。" }));
//                throw new Error(errorData.message || `学習サーバーエラー(Phase2): ${response.status}`);
//            }
//            const data = await response.json();
//            appendMessage(data.message || "Phase2 学習が完了しました。");
//            if (data.simulation_results) {
//                appendMessage("自己対戦シミュレーション結果:");
//                appendMessage(`  Agent1勝利: ${data.simulation_results.agent1_win}`);
//                appendMessage(`  Agent2勝利: ${data.simulation_results.agent2_win}`); // Python側とキーを合わせる
//                appendMessage(`  引き分け: ${data.simulation_results.draw}`);
//            }
//        } catch (error) {
//            console.error("Error in Phase2 training:", error);
//            appendMessage(`Phase2 学習エラー: ${error.message}`);
//        } finally {
//            learnButton.disabled = false;
//            learn2Button.disabled = false;
//            playButton.disabled = false;
//        }
//    });
//} else {
//    console.warn("learn2-button がHTML内に見つかりません。");
//}
// ここまで


// プレイボタン
playButton.addEventListener("click", () => {
    // modeSelectionDiv を参照している箇所を削除またはコメントアウト
    // modeSelectionDiv.style.display = "none"; // ← この行を削除またはコメントアウト
    document.getElementById("rules-section").style.display = "none";
    document.getElementById("ruletwo-section").style.display = "none";
    document.getElementById("play-selection").style.display = "none";
    document.getElementById("warning-message").style.display = "none";
    document.getElementById("warningtwo-message").style.display = "none";
    gameContainerDiv.style.display = "block";
    startGame();
});

//「次のゲームへ」ボタンの処理
nextGameButton.addEventListener('click', () => {
    // startGame() 関数を呼び出して新しいゲームを開始する
    // startGame() は内部で /start_game を呼び出し、画面を初期化してくれる
    appendMessage("--------------------"); // 区切り線
    appendMessage("次のゲームを開始します...");
    startGame();
});

// 終了ボタンの処理
resetAllButton.addEventListener('click', async () => {
    // 確認ダイアログを出す (任意)
    if (!confirm("本当に終了して全てのデータをリセットしますか？ (ポイントやSPカードも初期化されます)")) {
        return; // キャンセルされたら何もしない
    }

    // ボタンを無効化 (連打防止)
    resetAllButton.disabled = true;

    try {
        const response = await fetch('/reset_all', { method: 'POST' });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "リセット処理でエラーが発生しました。");
        }

        // リセット成功メッセージを表示 (任意)
        alert(data.message + "\nページを再読み込みして最初から始めます。");

        // ページをリロードして初期画面に戻す
        location.reload();

    } catch (error) {
        console.error("Error resetting session:", error);
        alert(`リセットエラー: ${error.message}`);
        // エラー時はボタンを再度有効にする
        resetAllButton.disabled = false;
    }
});
