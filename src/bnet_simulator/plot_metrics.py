import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

RESULTS_DIR = "simulation_results"

def load_all_metrics():
    data = []
    for csv_file in glob.glob(os.path.join(RESULTS_DIR, "*.csv")):
        df = pd.read_csv(csv_file, index_col=0, header=0)
        row = df["Value"].to_dict()
        row["filename"] = os.path.basename(csv_file)
        data.append(row)
    return pd.DataFrame(data)

def plot_metrics(df):
    for metric in ["Delivery Ratio", "Collisions", "Avg Latency"]:
        plt.figure()
        for sched_type in df["Scheduler Type"].unique():
            subset = df[df["Scheduler Type"] == sched_type]
            plt.plot(subset["Mobile Buoys"], subset[metric], marker="o", label=sched_type)
        plt.xlabel("Mobile Buoys")
        plt.ylabel(metric)
        plt.title(f"{metric} vs Mobile Buoys")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(RESULTS_DIR, f"{metric.replace(' ', '_').lower()}.png"))
        plt.close()

def main():
    df = load_all_metrics()
    plot_metrics(df)
    print("Plots saved in", RESULTS_DIR)

if __name__ == "__main__":
    main()