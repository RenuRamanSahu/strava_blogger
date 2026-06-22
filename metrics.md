# Metrics & Formulas Reference

All mathematical formulas and derived metrics used across the codebase.

---

## 1. Pace Calculations

### Speed → Pace (strava.py)

$$\text{pace (s/km)} = \frac{1000}{\text{speed (m/s)}}$$

$$\text{minutes} = \lfloor \text{pace} / 60 \rfloor, \quad \text{seconds} = \text{pace} \bmod 60$$

### Speed → Decimal Pace — `_speed_to_pace()` (strava.py)

$$\text{pace (min/km)} = \min\!\left(\frac{1000}{\text{speed (m/s)} \times 60},\; 15.0\right)$$

Capped at 15.0 min/km to handle near-zero speeds (stops, GPS drift).

---

## 2. Distance Conversions

$$\text{distance (km)} = \frac{\text{distance (m)}}{1000}$$

Applied to activity distance, gear cumulative distance, per-activity ACWR loop, and stream data points.

---

## 3. Training Load

### Per-Activity Training Load (strava.py)

$$\text{training load} = \text{duration (min)} \times \frac{\text{avg speed (m/s)}}{3.0}$$

Intensity is normalized so 3.0 m/s (~5:33/km) equals 1.0. Falls back to 0.5 if speed is zero.

### Acute Load (7-day)

$$\text{acute load} = \sum_{\text{last 7 days}} \text{training load}_i$$

### Chronic Load (28-day)

$$\text{chronic load} = \sum_{\text{last 28 days}} \text{training load}_i$$

### Chronic Weekly Average

$$\text{chronic weekly} = \frac{\text{chronic load}}{4}$$

### ACWR (Acute:Chronic Workload Ratio)

$$\text{ACWR} = \frac{\text{acute load (7d)}}{\text{chronic weekly avg}}$$

### ACWR Zone Classification

| ACWR Range | Status              | Injury Risk              |
|------------|---------------------|--------------------------|
| < 0.8      | Under-training      | Low (detraining risk)    |
| 0.8 – 1.3  | Optimal Zone        | Low                      |
| 1.3 – 1.5  | Overreaching        | Moderate                 |
| > 1.5      | Danger Zone         | High                     |

---

## 4. Duration / Time

### Seconds → Minutes

$$\text{duration (min)} = \frac{\text{moving time (s)}}{60}$$

### Stopped Time

$$\text{stopped time} = \text{elapsed time} - \text{moving time}$$

### Seconds → Hours / Minutes / Seconds (map_image.py)

$$\text{hours} = \left\lfloor \frac{t}{3600} \right\rfloor, \quad \text{mins} = \left\lfloor \frac{t \bmod 3600}{60} \right\rfloor, \quad \text{secs} = t \bmod 60$$

---

## 5. Elevation

### Chart Y-Axis Bounds (charts.py)

$$\text{padding} = \max\!\big(0.1 \times (\text{max alt} - \text{min alt}),\; 2\big)$$

$$y_{\min} = \text{min alt} - \text{padding}, \quad y_{\max} = \text{max alt} + \text{padding}$$

### Per-km Elevation Delta (charts.py)

$$\Delta\text{elevation} = \text{altitude}_{\text{end}} - \text{altitude}_{\text{start}}$$

---

## 6. Per-km Segment Statistics (charts.py)

### Average Pace

$$\bar{p} = \frac{\sum_{i} p_i}{n}$$

### Pace Range

$$p_{\text{fastest}} = \min(p_i), \quad p_{\text{slowest}} = \max(p_i)$$

### Pace Chart Y-Axis Bounds

$$\text{padding} = \max\!\big(0.1 \times (p_{\max} - p_{\min}),\; 0.3\big)$$

---

## 7. Stream Downsampling (strava.py)

Uniformly samples `max_points` (default 80) from full stream arrays:

$$\text{step} = \frac{n}{\text{max\_points}}, \quad \text{idx}_i = \lfloor i \times \text{step} \rfloor$$

---

## 8. ACWR Gauge Geometry (acwr_gauge.py)

### ACWR → Angle Mapping

$$\theta = 180° - \frac{\text{ACWR}}{2.0} \times 180°$$

| ACWR | Angle |
|------|-------|
| 0.0  | 180°  |
| 0.8  | 108°  |
| 1.0  | 90°   |
| 1.3  | 63°   |
| 1.5  | 45°   |
| 2.0  | 0°    |

### Polar → Cartesian (SVG coordinates)

$$x = c_x + r \cos(\theta), \quad y = c_y - r \sin(\theta)$$

Y is subtracted because SVG's Y-axis points downward.

### Needle Tip Position

$$n_x = c_x + L \cos(\theta_{\text{needle}}), \quad n_y = c_y - L \sin(\theta_{\text{needle}})$$

Where $L = r - 10$ (needle length shorter than arc radius).

### SVG Large-Arc Flag

$$\text{large\_arc} = \begin{cases} 1 & \text{if sweep} > 180° \\ 0 & \text{otherwise} \end{cases}$$

---

## 9. Weather

### API Selection — Days Ago (weather.py)

$$\text{days ago} = \lfloor \text{now(UTC)} - \text{activity start(UTC)} \rfloor_{\text{days}}$$

- ≤ 2 days → Forecast API
- \> 2 days → Archive API

### Feels-Like Display Threshold

$$|\text{feels like} - \text{actual temp}| \ge 2°\text{C}$$

Only shown when the difference is perceptible.

---

## 10. Time Window for Activity Fetch (strava.py)

$$\text{epoch} = \text{now(UTC)} - \text{days} \times 86400$$

Used as the `after` parameter for the Strava API to fetch recent activities.

---

## 11. Decimal Pace → min:sec Display

$$\text{minutes} = \lfloor p \rfloor, \quad \text{seconds} = \lfloor (p - \lfloor p \rfloor) \times 60 \rfloor$$

Used in route segment text (Python) and Chart.js tooltip callbacks (JavaScript).

---

## 12. HR-less Metrics (useful when no heart-rate available)

These metrics can be computed from GPS, speed, distance, time, elevation and stream data when heart-rate is missing.

- Average Speed / Pace
	- Store as `avg_speed_m_s` and `avg_pace_s_per_km`.
	- Formula: $\mathrm{avg\_speed} = \frac{distance\_m}{moving\_time\_s}$; $\mathrm{avg\_pace\_s/km} = \frac{1000}{\mathrm{avg\_speed}}$.

- Normalized Pace (elevation-adjusted)
	- Simple elevation penalty: $\mathrm{norm\_pace} = \mathrm{pace\_s} + k\times\frac{gain\_m}{distance\_km}$ where $k$ ≈ 2–6 s per meter/km (tune per athlete).

- Pace Variability (per-km)
	- Compute per-km paces $p_i$ then: $\mathrm{pace\_std} = \mathrm{stddev}(p_i)$ and $\mathrm{pace\_cv} = \frac{\mathrm{pace\_std}}{\mathrm{mean}(p_i)}$.
	- Useful for detecting intervals, surges, or pacing noise (higher = more variable).

- Negative/Positive Split Indicator
	- Compare first half vs second half pace: $\Delta = mean(p_{second}) - mean(p_{first})$ (negative = faster second half).

- Stop / Moving Ratio
	- $\mathrm{moving\_pct} = \frac{moving\_time}{elapsed\_time} \times 100$ — highlights stop-heavy activities (walk breaks, GPS pauses).

- Split-level Fast Segment Detection (intervals)
	- Flag segments where $p_{seg} < mean(p) - 2\times\mathrm{pace\_std}$ over repeated blocks → likely interval work.

- Runner Effort Proxy (pace × duration)
	- `effort_proxy = duration_mins * (threshold_pace_s_per_km / avg_pace_s_per_km)` where threshold_pace is goal or recent best; if unknown, use 5k pace estimate.

- Distance-normalized Elevation
	- $\mathrm{elev\_gain\_per\_km} = \frac{total\_elevation\_gain\_m}{distance\_km}$ — useful to explain slow pace on hilly days.

- Max/Mean Grade
	- From elevation stream compute max gradient and mean positive grade across uphill sections.

- Per-km Segment Stats
	- For each km: pace, elevation gain, time lost to stops. Useful inputs for `pace_variability` and interval detection.

- Stride & Cadence Proxies (if no cadence sensor)
	- If cadence not present, infer step frequency from GPS-derived speed + assumed stride length (approximation only) — include as optional/experimental.

- Route Difficulty Score
	- Combine elevation/km and distance to create a simple difficulty index: $Difficulty = distance\_km \times (1 + \alpha\times elev\_gain\_per\_km)$ where $\alpha$ ≈ 0.02–0.04.

- Training Load (GPS-based proxy)
	- Use existing training load formula (duration × normalized speed) from section 3. This requires no HR and feeds ACWR.

- Consistency / Fatigue Proxies (population-free)
	- Rising pace variability across recent runs, increased stopped time %, and sudden weekly distance jump (>25%) together indicate elevated fatigue/risk.

### Storage recommendations

- Add numeric columns to the DB for the most-used HR-less derived fields: `avg_speed_m_s`, `avg_pace_s_per_km`, `pace_cv`, `pace_std_s`, `moving_pct`, `elev_gain_per_km`, `difficulty`, `effort_proxy`, plus `metrics_json` (already present) to allow re-calculation.
- Store per-km splits as a JSON array in `metrics_json` or a separate table `splits(activity_id, km_index, pace_s, elev_gain_m, time_s)` for more advanced queries.

### Example quick calculations (python)

```python
import statistics
paces = [/* per-km pace in seconds */]
pace_std = statistics.pstdev(paces)
pace_cv = pace_std / statistics.mean(paces)
moving_pct = moving_time_s / elapsed_time_s * 100
elev_per_km = total_elev_m / max(distance_km, 0.001)
```

Implement these HR-less metrics in `db.save_activity` or a post-processing script to backfill existing records. Prioritize `avg_pace`, `pace_cv`, `moving_pct`, `elev_gain_per_km`, and the `training load` proxy so the AI can use them immediately for narrative hooks.

