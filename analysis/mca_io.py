import csv
import numpy as np
import plotly.graph_objects as go


def save_spectrum_csv(spectrum, filepath: str):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["channel", "counts"])

        for i, counts in enumerate(spectrum):
            writer.writerow([i, int(counts)])


def save_spectrum_html(
    spectrum, filepath: str = "spectrum.html", title: str = "MCA Spectrum"
):
    x = np.arange(len(spectrum))
    y = np.array(spectrum, dtype=np.uint32)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name="Spectrum",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Channel",
        yaxis_title="Counts",
        template="plotly_white",
    )

    fig.write_html(filepath)
