// Minimal Telegram Bot API helpers for Cloudflare Workers.

export function tg(token) {
  const base = "https://api.telegram.org/bot" + token + "/";
  const call = async (method, payload) => {
    const r = await fetch(base + method, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return r.json();
  };
  return {
    sendMessage: (chatId, text, extra = {}) =>
      call("sendMessage", {
        chat_id: chatId,
        text,
        parse_mode: "Markdown",
        disable_web_page_preview: true,
        ...extra,
      }),
    editMessageText: (chatId, msgId, text, extra = {}) =>
      call("editMessageText", {
        chat_id: chatId,
        message_id: msgId,
        text,
        parse_mode: "Markdown",
        disable_web_page_preview: true,
        ...extra,
      }),
    sendPhoto: (chatId, photo, caption, extra = {}) =>
      call("sendPhoto", {
        chat_id: chatId,
        photo,
        caption,
        parse_mode: "Markdown",
        ...extra,
      }),
    // Galerie aus 2–10 Bildern. media = [{ type:"photo", media:url, caption?, parse_mode? }].
    // Caption (falls gewünscht) gehört aufs ERSTE Element.
    sendMediaGroup: (chatId, media) =>
      call("sendMediaGroup", { chat_id: chatId, media }),
    answerCallbackQuery: (id, text = "") =>
      call("answerCallbackQuery", { callback_query_id: id, text }),
    deleteMessage: (chatId, msgId) =>
      call("deleteMessage", { chat_id: chatId, message_id: msgId }),
    editMessageReplyMarkup: (chatId, msgId, extra = {}) =>
      call("editMessageReplyMarkup", { chat_id: chatId, message_id: msgId, ...extra }),
    setMyCommands: (commands) => call("setMyCommands", { commands }),
  };
}

// Build an inline keyboard from rows of {text, data} buttons.
export function keyboard(rows) {
  return {
    reply_markup: {
      inline_keyboard: rows.map((row) =>
        row.map((b) => ({ text: b.text, callback_data: b.data }))
      ),
    },
  };
}

export function chunk(arr, n) {
  const out = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
}
