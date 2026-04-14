import numpy as np
import plotly.graph_objects as go


def plot_spectrum(spectrum, title: str = "MCA Spectrum"):
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

    fig.show()


def plot_last_buffer(
    last_buffer, last_scope_result=None, title: str = "Last Acquired Buffer"
):
    if last_buffer is None:
        print("No buffer acquired yet.")
        return

    x = np.arange(len(last_buffer))
    y = np.array(last_buffer, dtype=float)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name="Buffer",
        )
    )

    if last_scope_result is not None:
        r = last_scope_result

        fig.add_vline(
            x=r.trigger_index_estimate,
            line_dash="dash",
            annotation_text="Trigger",
            annotation_position="top right",
        )

        fig.add_vline(
            x=r.peak_index,
            line_dash="dot",
            annotation_text="Peak",
            annotation_position="top left",
        )

        fig.add_hline(
            y=r.baseline,
            line_dash="dot",
            annotation_text="Baseline",
            annotation_position="bottom right",
        )

    fig.update_layout(
        title=title,
        xaxis_title="Sample index",
        yaxis_title="Voltage [V]",
        template="plotly_white",
    )

    fig.show()
