# gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/scriptstealer/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/scriptstealer/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast GTA VI's launch-day Twitch viewers hour by hour. A shape model built from past console launches: each comparable's release-day hourly curve divided by its hour-1 print, with a size adjustment that flattens the curve for bigger launches. It predicts five quantiles (5%, 25%, 50%, 75%, 95%) of the concurrent viewers for hours 2-24 of the release day, scored by pinball loss on the log scale.

How it works: only console-only launches with a rolling midnight-local unlock share GTA VI's shape, so PC-simultaneous and early-access launches are left out. The median ratio curve across that group dips in the dead of night, climbs as Europe wakes and the US coasts unlock, and peaks in the late UTC evening. The curve's amplitude is damped by a factor fitted from the size relation (log peak ratio falls about 0.32 per unit of log first-hour print), so a huge launch like GTA VI gets a flatter forecast than a small one. Quantiles come from the spread of log ratios across the group at each hour. Standard library only, no network, fully deterministic.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=6rdgs9pm&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
