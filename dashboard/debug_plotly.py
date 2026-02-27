from utils import plotly_snapshot_chart

labels = ["A very long chapter name for testing labels", "Chapter B", "Chapter C"]
values = [12.3, 8.4, 5.1]

fig = plotly_snapshot_chart(labels, values, theme="light")
print("Snapshot chart created successfully. Layout keys:")
print(sorted(fig.to_plotly_json().get("layout", {}).keys()))
