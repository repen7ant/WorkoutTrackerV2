import { tabs } from "./dom.js";
import { showList } from "./list.js";
import { showProgress } from "./progress.js";
import { inTelegram, tg } from "./telegram.js";

tabs.workouts.onclick = () => showList();
tabs.progress.onclick = () => showProgress();
tg.ready();
tg.expand();
if (inTelegram && tg.isVersionAtLeast("6.1")) {
  // шапка и фон Telegram того же цвета, что и страница
  tg.setHeaderColor("secondary_bg_color");
  tg.setBackgroundColor("secondary_bg_color");
}
showList();
