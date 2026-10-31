import { notify, tg } from "./telegram.js";

export async function api(method, path, body) {
  const options = { method, headers: { Authorization: `tma ${tg.initData}` } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (e) {
    notify("No connection. Check the network and try again.");
    throw e;
  }
  if (response.status === 401) {
    notify("Session expired. Reopen the app from /history.");
    throw new Error("unauthorized");
  }
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || `Request failed (${response.status})`;
    notify(message);
    throw new Error(message);
  }
  return data;
}
