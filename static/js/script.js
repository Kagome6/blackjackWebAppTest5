// テーマ切り替え用
document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;

    // --- 新しいトグルスイッチの制御 ---
    const themeToggleCheckbox = document.getElementById('theme-toggle-checkbox');

    // 画像要素を取得
    const playImage = document.getElementById('play-image');           
    const resetImage = document.getElementById('reset-image');
    const hitImage = document.getElementById('hit-image');
    const standImage = document.getElementById('stand-image');
    const nextGameImage = document.getElementById('next-game-image');

    // パスを直接文字列で指定する
    const imagePaths = {
        light: {
            play:  '/static/images/play_button.png',                   // (ライトモード用画像)
            reset: '/static/images/end_button.png',
            hit:   '/static/images/hit_button.png',
            stand: '/static/images/stand_button.png',
            next:  '/static/images/next_game_button.png'
        },
        dark: {
            play:  '/static/images/play_button_dark.png',              // (ダークモード用画像)
            reset: '/static/images/end_button_dark.png',
            hit:   '/static/images/hit_button_dark.png',
            stand: '/static/images/stand_button_dark.png',
            next:  '/static/images/next_game_button_dark.png'
        }
    };

    // テーマを適用する関数
    function applyTheme(theme) {
        if (theme === 'dark') {
            body.classList.add('dark-mode');
            // 画像をダークモード用に変更
            if (playImage) playImage.src = imagePaths.dark.play;
            if (resetImage) resetImage.src = imagePaths.dark.reset;
            if (hitImage) hitImage.src = imagePaths.dark.hit;
            if (standImage) standImage.src = imagePaths.dark.stand;
            if (nextGameImage) nextGameImage.src = imagePaths.dark.next;
        } else {
            body.classList.remove('dark-mode');
            // 画像をライトモード用に変更
            if (playImage) playImage.src = imagePaths.light.play;
            if (resetImage) resetImage.src = imagePaths.light.reset;
            if (hitImage) hitImage.src = imagePaths.light.hit;
            if (standImage) standImage.src = imagePaths.light.stand;
            if (nextGameImage) nextGameImage.src = imagePaths.light.next;
        }
    }

    // --- イベントリスナーを新しいチェックボックス用に変更 ---
    themeToggleCheckbox.addEventListener('change', () => {
        // チェックボックスがONなら'dark'、OFFなら'light'
        const newTheme = themeToggleCheckbox.checked ? 'dark' : 'light';
        localStorage.setItem('theme', newTheme);
        applyTheme(newTheme);
    });

    // --- ページ読み込み時の処理を修正 ---
    const savedTheme = localStorage.getItem('theme') || 'light';
    // 保存されたテーマに合わせて、チェックボックスの初期状態をセット
    if (savedTheme === 'dark') {
        themeToggleCheckbox.checked = true;
    }
    // テーマを適用
    applyTheme(savedTheme);
});


// DOM要素の取得
// ↓↓↓メンテナンス時以外はコメントアウトしておく ↓↓↓
//const modeSelectionDiv = document.getElementById("mode-selection");
//const learnButton = document.getElementById("learn-button");
//const learn2Button = document.getElementById("learn2-button");
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
const declarableSpCardsDiv = document.getElementById("declarable-sp-cards");
const instantSpCardsDiv = document.getElementById("instant-sp-cards");


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
 * @param {string|null} declaredCardId - 現在プレイヤーが宣言中のカードID (なければ null or undefined)
 */
function updateSpCardsDisplay(spCards, declaredCardId) {
    console.log("DEBUG: updateSpCardsDisplay called. spCards:", JSON.stringify(spCards), "declaredCardId:", declaredCardId); // ★デバッグ追加★
    
    // HTML要素の取得 (関数の冒頭にまとめる)
    const declarableSpCardsDiv = document.getElementById("declarable-sp-cards");
    const instantSpCardsDiv = document.getElementById("instant-sp-cards");
    const declaredCardNameSpan = document.getElementById("declared-card-name");
    const aiDeclaredCardNameSpan = document.getElementById("ai-declared-card-name"); // AIの宣言表示用
    const hitButton = document.getElementById("hit-button"); // プレイヤーのターン判定用

    if (!declarableSpCardsDiv) console.error("DEBUG: declarable-sp-cards div not found!");
    if (!instantSpCardsDiv) console.error("DEBUG: instant-sp-cards div not found!");
    if (!declaredCardNameSpan) console.error("DEBUG: declared-card-name span not found!");
    if (!aiDeclaredCardNameSpan) console.warn("DEBUG: ai-declared-card-name span not found! AI declaration status may not work correctly."); // 警告に変更
    if (!hitButton) console.error("DEBUG: hit-button not found! Player turn check may not work correctly.");

    // 表示エリアをクリア
    if (declarableSpCardsDiv) declarableSpCardsDiv.innerHTML = '';
    if (instantSpCardsDiv) instantSpCardsDiv.innerHTML = '';

    // プレイヤーの宣言中カード表示の更新
    if (declaredCardNameSpan) { // 要素が存在する場合のみ処理
        if (declaredCardId && SP_CARDS_MASTER_JS && SP_CARDS_MASTER_JS[declaredCardId]) {
            declaredCardNameSpan.textContent = SP_CARDS_MASTER_JS[declaredCardId].name || declaredCardId;
        } else if (declaredCardId) {
            declaredCardNameSpan.textContent = declaredCardId;
        } else {
            declaredCardNameSpan.textContent = 'なし';
        }
    }

    if (!spCards || Object.keys(spCards).length === 0) {
        console.log("DEBUG: No SP cards data or empty spCards object."); // ★デバッグ追加★
        if (declarableSpCardsDiv) declarableSpCardsDiv.innerHTML = '<p>なし</p>';
        if (instantSpCardsDiv) instantSpCardsDiv.innerHTML = '<p>なし</p>';
        return;
    }

    console.log("DEBUG: SP_CARDS_MASTER_JS:", JSON.stringify(SP_CARDS_MASTER_JS));
    
    let declarableCardsCount = 0;
    let instantCardsCount = 0;

    // --- AIが何か宣言系カードを宣言中かどうかの判定 (ループの前に一度だけ行う) ---
    // aiDeclaredCardNameSpan が存在し、かつテキストが「なし」や空でない場合に true
    const aiIsDeclaring = aiDeclaredCardNameSpan ? 
                          (aiDeclaredCardNameSpan.textContent !== 'なし' && aiDeclaredCardNameSpan.textContent !== '') : 
                          false;
    console.log("DEBUG: Initial check - aiIsDeclaring:", aiIsDeclaring, "(Based on aiDeclaredCardNameSpan.textContent:", aiDeclaredCardNameSpan ? aiDeclaredCardNameSpan.textContent : "Element not found or null", ")");


    for (const cardId in spCards) {
        console.log(`DEBUG: Processing cardId: ${cardId}, Count: ${spCards[cardId]}`);
        const count = spCards[cardId];

        if (count > 0) { // 所持数が1以上なら表示処理
            const cardMasterInfo = SP_CARDS_MASTER_JS[cardId];

            if (!cardMasterInfo) {
                console.warn(`DEBUG: SP_CARDS_MASTER_JS missing info for: ${cardId}. This card will not be displayed.`);
                continue; // マスター情報がなければこのカードは表示しない
            }
            console.log(`DEBUG: cardMasterInfo for ${cardId}: ${JSON.stringify(cardMasterInfo)}, Type: ${cardMasterInfo.type}`);

            // カードアイテムのコンテナを作成
            const cardInfoDiv = document.createElement('div');
            cardInfoDiv.classList.add('sp-card-item');

            // カード名と所持数の表示
            const cardName = cardMasterInfo.name || cardId; // マスター名がなければID
            const cardCountText = ` x ${count}`;
            const cardTextSpan = document.createElement('span');
            cardTextSpan.textContent = `${cardName}${cardCountText} `;
            cardInfoDiv.appendChild(cardTextSpan);

            // 「使用」ボタンの作成
            const useButton = document.createElement('button');
            useButton.textContent = '使用';
            useButton.classList.add('use-sp-button');
            useButton.dataset.cardId = cardId;

            // ボタンの有効/無効化ロジック
            let buttonDisabled = false;
            // hitButton が存在し、かつ disabled であればプレイヤーのターンではない
            const isNotPlayerTurn = hitButton ? hitButton.disabled : true; 
            // declaredCardId はプレイヤーが宣言中のカードID (関数の引数)

            if (cardMasterInfo.type === "instant") {
                // 即時発動系カード (例: 手札戻し)
                // 条件: プレイヤーのターンであること
                buttonDisabled = isNotPlayerTurn;
            } else if (cardMasterInfo.type === "declare") {
                // 宣言系カード (例: ポイント-3)
                // 条件: プレイヤーのターンであること
                //       かつ、プレイヤー自身が何も宣言していないこと (declaredCardId が null または空)
                //       かつ、AIも何も宣言系カードを宣言していないこと (aiIsDeclaring が false)
                buttonDisabled = isNotPlayerTurn || !!declaredCardId || aiIsDeclaring;
            } else {
                console.warn(`未定義または不明なSPカードタイプ: ${cardId}, Type: ${cardMasterInfo.type}. Button will be disabled.`);
                buttonDisabled = true; // 不明なタイプは安全のために無効化
            }
            useButton.disabled = buttonDisabled;

            // ボタン状態のデバッグログ (ループ内、各ボタンごとに出力)
            console.log(`DEBUG: Button for ${cardId} - Type: ${cardMasterInfo.type}, isNotPlayerTurn: ${isNotPlayerTurn}, playerDeclaredId: ${declaredCardId}, aiIsDeclaring: ${aiIsDeclaring}, Resulting buttonDisabled: ${buttonDisabled}`);

            useButton.addEventListener('click', handleUseSpCard);
            cardInfoDiv.appendChild(useButton);

            // カードの種類に応じて適切な表示コンテナに追加
            if (cardMasterInfo.type === "instant") {
                if (instantSpCardsDiv) {
                    instantSpCardsDiv.appendChild(cardInfoDiv);
                    instantCardsCount++; // 表示したカードの数をカウント
                } else {
                    console.warn("instant-sp-cards の表示エリアが見つかりません。");
                }
            } else if (cardMasterInfo.type === "declare") {
                if (declarableSpCardsDiv) {
                    declarableSpCardsDiv.appendChild(cardInfoDiv);
                    declarableCardsCount++; // 表示したカードの数をカウント
                } else {
                    console.warn("declarable-sp-cards の表示エリアが見つかりません。");
                }
            } else {
                // typeが未定義または不明なカードはここでは表示しない
                console.log(`Card ${cardId} with unknown type '${cardMasterInfo.type}' was not added to any display list.`);
            }
        }
    }

    // 各コンテナにカードが一つも表示されなかった場合に「なし」と表示
    if (declarableSpCardsDiv && declarableCardsCount === 0) {
        declarableSpCardsDiv.innerHTML = '<p>なし</p>';
    }
    if (instantSpCardsDiv && instantCardsCount === 0) {
        instantSpCardsDiv.innerHTML = '<p>なし</p>';
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

// --- SPカードのマスター情報をJSでも保持 ---
// 本来はサーバーから取得するのが望ましいが、一旦ここで定義
const SP_CARDS_MASTER_JS = {
    "sp_minus_3": { 
        "name": "ポイント-3", 
        "description": "相手のポイントを3減らす",
        "type": "declare" // "declare" を追加
    },
    "sp_return_last_card": {
        "name": "手札戻し",
        "description": "最後に引いたカード1枚を山札に戻す。",
        "type": "instant" //"instant" を追加
    }
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
    appendMessage(`'${cardName}' の使用を使用します...`);　// 「宣言」から「使用」に変更

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

        // エラー復帰処理のために、成功した時点のSPカード状態を保存する
        sessionStorage.setItem('last_player_sp_cards', JSON.stringify(data.player_sp_cards));
        sessionStorage.setItem('last_declared_sp_card', data.declared_sp_card || '');

        // --- ボタン状態の更新 (API応答後) ---
        // 即時発動系カードの場合、プレイヤーのターンが続くことが多い
        // 宣言系カードの場合も、宣言後にプレイヤーが続けて行動できる
        if (!data.game_over) { // ゲームが続いていれば
             hitButton.disabled = false;
             standButton.disabled = false;
        } else { // (ほぼありえないが) SPカード使用でゲームオーバーになった場合
             hitButton.disabled = true;
             standButton.disabled = true;
             if (typeof endGameDiv !== 'undefined') endGameDiv.style.display = "block";
        }

        // --- 表示更新 (ボタン状態が確定した後) ---
        updatePointsDisplay(data.player_points, data.ai_points);
        // 手札表示は宣言では変わらないので不要
        // updateCards(data.player_hand, data.ai_hand);
        appendMessage(data.message); // サーバーからのメッセージを表示

        // 「手札戻し」カード使用による手札更新
        if (data.player_hand_updated && data.player_hand) {
            // data.player_hand には更新されたプレイヤーの手札が、
            // data.ai_hand には (変更ないはずだが念のため) AIの手札表示用データが入っている想定
            updateCards(data.player_hand, data.ai_hand); 
            appendMessage("あなたの手札が更新されました。");
        }
        
        // SPカードリストと宣言状態の表示更新
        // data.declared_sp_card は宣言系カードの場合にセットされる
        updateSpCardsDisplay(data.player_sp_cards, data.declared_sp_card || null);
        updateAISpCardsDisplay(data.ai_sp_cards);
        updateAIDeclaredCardDisplay(data.ai_declared_sp_card || null);        

    } catch (error) {
        // ------------------- ここから修正版 -------------------
        console.error("Error using SP card:", error);
        
        // 1. ユーザーにエラーメッセージを通知
        // error.message には fetch('/use_sp_card') の try ブロックで投げられた
        // サーバーからの具体的なエラー内容 (data.error) が入る
        appendMessage(`SPカード使用エラー: ${error.message}`);

        // 2. ゲームが終了していない場合のみ、操作ボタンを有効に戻す
        //    (ゲーム終了画面が表示されている場合は、ボタンは無効のままにする)
        const isGameScreenActive = !document.getElementById("end-game") || document.getElementById("end-game").style.display === "none";
        
        if (isGameScreenActive) {
            hitButton.disabled = false;
            standButton.disabled = false;
        }

        // 3. SPカードの表示状態をエラー発生前の状態に復元する
        //    (この処理は、API通信が成功した際にsessionStorageに最新状態を保存していることが前提)
        try {
            const lastPlayerSpCards = JSON.parse(sessionStorage.getItem('last_player_sp_cards') || '{}');
            const lastDeclaredCard = sessionStorage.getItem('last_declared_sp_card') || null;
            
            // SPカード表示更新関数を呼び出し、UIをエラー前の状態に戻す
            // これにより、他のSPカードボタンも適切に有効/無効化される
            updateSpCardsDisplay(lastPlayerSpCards, lastDeclaredCard);

        } catch (storageError) {
            console.error("Failed to restore SP cards display from sessionStorage:", storageError);
            // sessionStorageからの復元に失敗した場合のフォールバック
            // (最悪のケースとして、全てのSPボタンを一旦有効にするなど)
            document.querySelectorAll('.use-sp-button').forEach(btn => {
                if(isGameScreenActive) btn.disabled = false;
            });
        }

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
        appendMessage("山札にもうカードがありません。もしくはエラー？");
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
//    console.warn("learn-button がHTML内に見つかりません。");
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
