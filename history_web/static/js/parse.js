// Разбор полей формы. Ошибка — текст, который увидит пользователь.

export function parseWeight(text) {
  const value = text.trim().replace(",", ".");
  if (value === "" || value.toLowerCase() === "bw") return null;
  if (!/^\d+(\.\d+)?$/.test(value)) throw new Error(`Invalid weight: ${text}`);
  return Number(value);
}

export function parseAmount(text, unit) {
  const value = text.trim();
  let amount = NaN;
  if (unit === "reps" && /^\d+$/.test(value)) amount = Number(value);
  if (unit === "sec") {
    const time = value.match(/^(\d+):([0-5]\d)$/);
    if (time) amount = Number(time[1]) * 60 + Number(time[2]);
    else if (/^\d+s?$/.test(value)) amount = parseInt(value, 10);
  }
  if (!(amount > 0)) throw new Error(unit === "reps" ? `Invalid reps: ${text}` : `Invalid time: ${text}`);
  return amount;
}
