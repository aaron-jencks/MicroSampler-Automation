import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

EPS = 1

def row_score(pv, c0m, c1m, it, s0, s1):
    sig_score = min(-np.log10(max(pv, 1e-300)) / 10.0, 1.0)
    effect_score = abs(c0m - c1m) / (c0m + c1m + EPS)
    iter_score = 1.0 - np.exp(-it / 30.0)
    balance_score = 100.0 * (1.0 - (abs(s0-s1) / (s0+s1)))

    return sig_score * effect_score * iter_score * balance_score


def compute_curve(pv, c0m, c1m, s0, s1):
    iterations = np.arange(1, 5001)
    scores = np.array([
        row_score(pv, c0m, c1m, it, s0, s1)
        for it in iterations
    ])
    return iterations, scores


# Initial values
init = {
    "pv": 0.05,
    "c0m": 100.0,
    "c1m": 110.0,
    "s0": 250,
    "s1": 250,
    "threshold": 1.0,
}

fig, ax = plt.subplots(figsize=(10, 6))
plt.subplots_adjust(left=0.1, bottom=0.42)

x, y = compute_curve(
    init["pv"],
    init["c0m"],
    init["c1m"],
    init["s0"],
    init["s1"],
)

[line] = ax.plot(x, y, linewidth=2)
threshold_line = ax.axhline(init["threshold"], linestyle="--")

ax.set_title("Side-channel row score vs iteration")
ax.set_xlabel("Iteration")
ax.set_ylabel("Score")
ax.grid(True)

text = ax.text(
    0.02,
    0.95,
    "",
    transform=ax.transAxes,
    va="top",
    bbox=dict(boxstyle="round", alpha=0.15),
)

# Slider axes
ax_pv = plt.axes([0.15, 0.32, 0.7, 0.03])
ax_c0m = plt.axes([0.15, 0.27, 0.7, 0.03])
ax_c1m = plt.axes([0.15, 0.22, 0.7, 0.03])
ax_s0 = plt.axes([0.15, 0.17, 0.7, 0.03])
ax_s1 = plt.axes([0.15, 0.12, 0.7, 0.03])
ax_threshold = plt.axes([0.15, 0.07, 0.7, 0.03])

# Use p-value exponent slider: pv = 10^-x
pv_slider = Slider(ax_pv, "p-value", 0.0, 1.0, valinit=-np.log10(init["pv"]))
c0m_slider = Slider(ax_c0m, "c0 mean", 1.0, 1000.0, valinit=init["c0m"])
c1m_slider = Slider(ax_c1m, "c1 mean", 1.0, 1000.0, valinit=init["c1m"])
s0_slider = Slider(ax_s0, "s0 samples", 1, 5000, valinit=init["s0"], valstep=1)
s1_slider = Slider(ax_s1, "s1 samples", 1, 5000, valinit=init["s1"], valstep=1)
threshold_slider = Slider(ax_threshold, "threshold", 0.0, 20.0, valinit=init["threshold"])


def update(_=None):
    pv = float(pv_slider.val)
    c0m = c0m_slider.val
    c1m = c1m_slider.val
    s0 = int(s0_slider.val)
    s1 = int(s1_slider.val)
    threshold = threshold_slider.val

    x, y = compute_curve(pv, c0m, c1m, s0, s1)

    line.set_ydata(y)
    threshold_line.set_ydata([threshold, threshold])

    max_score = np.max(y)
    final_score = y[-1]

    above = np.where(y >= threshold)[0]
    if len(above) > 0:
        first_hit = x[above[0]]
        hit_msg = f"Threshold reached at iteration {first_hit}"
    else:
        hit_msg = "Threshold not reached"

    sig_score = min(-np.log10(max(pv, 1e-300)) / 10.0, 1.0)
    effect_score = abs(c0m - c1m) / (c0m + c1m + EPS)
    balance = 100.0 / (1.0 + abs(s0 - s1) / (s0 + s1 + EPS))

    text.set_text(
        f"pv = {pv:.2e}\n"
        f"sig_score = {sig_score:.3f}\n"
        f"effect_score = {effect_score:.4f}\n"
        f"balance multiplier = {balance:.2f}\n"
        f"final score @ 5000 = {final_score:.3f}\n"
        f"max score = {max_score:.3f}\n"
        f"{hit_msg}"
    )

    ax.set_ylim(0, max(1.0, max_score, threshold) * 1.15)
    fig.canvas.draw_idle()


for slider in [
    pv_slider,
    c0m_slider,
    c1m_slider,
    s0_slider,
    s1_slider,
    threshold_slider,
]:
    slider.on_changed(update)

update()
plt.show()
