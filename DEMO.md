# 5-minute demo script (synthetic data; works with Wi-Fi off except map tiles)

Start: `make demo`, open <http://localhost:5173>. Keep the yellow "Synthetic simulation data" banner in view throughout.

1. **Base day (0:00-1:00).** *Map & plan* tab, `Recovery-aware prize`. Bins are coloured by overflow risk (switch to recovery value); fill size shows how full each bin is; coloured lines are one vehicle trip each;
   hollow bins were not collected; coloured dots are facilities (DWCC, wet plant, biomethanation, landfill). Drag the day slider.
2. **Generation +20 % (1:00-1:45).** Move *Waste generation per person* to +20 and run: overflow and cost rise (answers from the precomputed grid, instantly; the badge says "precomputed").
3. **Segregation 50 % -> 90 % (1:45-2:30).** Recovered value rises and the landfill share of collected mass falls; the flow chart in *Compare scenarios* shows composting / recycling / landfill per day.
4. **Remove a vehicle (2:30-3:15).** *Vehicles out of service* = 1 (then 2): points dropped despite a prize (dashed) appear and overflow events increase.
5. **Raise facility capacity (3:15-3:45).** Facility capacity +100 %: facility over-capacity days and landfill share fall (the dry-recyclable DWCC capacity is the binding one in the base case).
6. **Side by side (3:45-4:30).** Press *Overflow-only vs recovery-aware (these levers)*: KPI cards and daily flows for both policies, with the difference table.
7. **Evidence (4:30-5:00).** *Policy results* tab: 10-seed policy comparison, paired Wilcoxon tests, alpha-beta trade-off / Pareto front. Close with the limitations: synthetic bins and `TODO-SOURCE` placeholders.

Backup: record the screen once with the macOS screen recorder (Shift-Cmd-5) and keep the file next to this script (not committed).
