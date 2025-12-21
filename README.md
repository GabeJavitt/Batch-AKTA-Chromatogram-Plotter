# ÄKTA Chromatogram Batch Plotter

A standalone Python script to automatically batch process ÄKTA UNICORN result `.zip` files and generate high-quality chromatogram plots. This tool is designed for modern *UNICORN 6+* result files and has no external dependency on the `PyCORN` library.

![Example Chromatogram Plot](sample.png)

---

## Description

This script provides a simple command-line interface to automate the tedious task of exporting chromatograms. Point it at a folder of your ÄKTA `.zip` files, and it will generate a `.png` plot for each one, saving you time and ensuring consistent output for reports and analysis.

The core parsing logic for the UNICORN 6 format is integrated directly into the script, so you don't need to install or troubleshoot the `PyCORN` library.

---

## Features

- **Batch Processing**: Process an entire folder of `.zip` files with a single command.
- **Standalone**: No `PyCORN` dependency. The necessary code is built-in.
- **Highly Customizable Plots**:
  - Choose exactly which data curves to display (e.g., UV, conductivity, pH).
  - Manually set X and Y-axis limits for standardized, comparable graphs.
- **Smart Defaults**: If no curves are specified, the script automatically plots the most common traces (UV, Conductivity, and Gradient).
- **Multi-Axis Support**: Automatically creates up to three Y-axes to keep plots with different scales readable.
- **High-Quality Output**: Saves plots as 300 DPI `.png` files suitable for presentations and publications.

---

## Requirements

- Python 3.x
- `matplotlib`
- `xmltodict`

---

## Setup

1.  **Clone or Download**: Get the `batch_chromatogram_plotter.py` script from this repository.
2.  **Install Dependencies**: Open your terminal or command prompt and install the required Python libraries using pip.
    ```bash
    pip install matplotlib xmltodict
    ```

---

## Usage

Run the script from your terminal. You must provide an input directory (where your `.zip` files are) and an output directory (where the plots will be saved).

### Basic Syntax

```bash
python BatchChromatogramPlotter.py <path/to/input_folder> <path/to/output_folder> [options]
