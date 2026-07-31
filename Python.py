# Import pandas for reading and analysing the CSV file
import pandas as pd

# Import matplotlib for creating graphs
import matplotlib.pyplot as plt


# Read the DHT11 CSV file
# The CSV file must be in the same folder as this Python file
data = pd.read_csv("dht11_data.csv")


# Convert the timestamp column from text into date and time values
data["timestamp"] = pd.to_datetime(
    data["timestamp"],
    errors="coerce"
)

# Convert the elapsed time into numbers
data["elapsed_seconds"] = pd.to_numeric(
    data["elapsed_seconds"],
    errors="coerce"
)

# Convert temperature into numbers
data["temperature_c"] = pd.to_numeric(
    data["temperature_c"],
    errors="coerce"
)

# Convert humidity into numbers
data["humidity_percent"] = pd.to_numeric(
    data["humidity_percent"],
    errors="coerce"
)


# Check whether the CSV contains missing values
print("Missing values:")
print(data.isna().sum())

# Check whether the CSV contains duplicate rows
print("Duplicate rows:", data.duplicated().sum())


# Remove rows containing missing values
data = data.dropna()

# Remove duplicate rows
data = data.drop_duplicates()


# Display the number of valid readings
print("Valid readings:", len(data))

# Display the test duration in minutes
duration_minutes = (
    data["elapsed_seconds"].max()
    - data["elapsed_seconds"].min()
) / 60

print("Test duration:", round(duration_minutes, 2), "minutes")


# Calculate and display the statistics
statistics = data[
    ["temperature_c", "humidity_percent"]
].describe()

print("\nTemperature and humidity statistics:")
print(statistics)


# PLOT 1: MEASUREMENTS OVER TIME

# Create two graphs arranged vertically
fig, axes = plt.subplots(2, 1, figsize=(10, 7))

# Create the temperature line graph
axes[0].plot(
    data["timestamp"],
    data["temperature_c"],
    color="blue"
)

# Add the temperature graph title and label
axes[0].set_title("Temperature Over Time")
axes[0].set_ylabel("Temperature (C)")
axes[0].grid(True)


# Create the humidity line graph
axes[1].plot(
    data["timestamp"],
    data["humidity_percent"],
    color="green"
)

# Add the humidity graph title and labels
axes[1].set_title("Humidity Over Time")
axes[1].set_ylabel("Humidity (% RH)")
axes[1].set_xlabel("Time")
axes[1].grid(True)


# Improve the spacing between the graphs
plt.tight_layout()

# Save the first figure
plt.savefig("plot_1_time_series.png", dpi=300)

print("Saved: plot_1_time_series.png")

# Display the first figure
plt.show()


# PLOT 2: DATA DISTRIBUTIONS

# Create two graphs arranged horizontally
fig, axes = plt.subplots(1, 2, figsize=(10, 4))


# Create the temperature histogram
axes[0].hist(
    data["temperature_c"],
    color="blue",
    edgecolor="black"
)

# Add the temperature histogram labels
axes[0].set_title("Temperature Distribution")
axes[0].set_xlabel("Temperature (C)")
axes[0].set_ylabel("Number of Readings")
axes[0].grid(axis="y")


# Create the humidity histogram
axes[1].hist(
    data["humidity_percent"],
    color="green",
    edgecolor="black"
)

# Add the humidity histogram labels
axes[1].set_title("Humidity Distribution")
axes[1].set_xlabel("Humidity (% RH)")
axes[1].set_ylabel("Number of Readings")
axes[1].grid(axis="y")


# Improve the spacing between the graphs
plt.tight_layout()

# Save the second figure
plt.savefig("plot_2_distributions.png", dpi=300)

print("Saved: plot_2_distributions.png")

# Display the second figure
plt.show()


# Tell the user that the analysis is finished
print("Part D analysis finished.")
