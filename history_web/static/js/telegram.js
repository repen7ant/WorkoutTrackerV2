export const tg = window.Telegram.WebApp;
// вне Telegram (dev_link в браузере) нативных попапов нет
export const inTelegram = tg.platform !== "unknown";

export function notify(message) {
  if (inTelegram) tg.showAlert(message);
  else window.alert(message);
}

export function confirmAction(message) {
  return new Promise((resolve) => {
    if (inTelegram) tg.showConfirm(message, resolve);
    else resolve(window.confirm(message));
  });
}
