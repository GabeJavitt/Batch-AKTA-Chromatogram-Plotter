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

```

# ÄKTA Smart Plotter Pro

A high-performance GUI application designed to automatically batch process ÄKTA UNICORN™ result `.zip` files and generate publication-quality chromatogram plots.

---

## Description

**ÄKTA Smart Plotter Pro** provides a modern, user-friendly interface to automate the extraction and visualization of protein purification data. Designed specifically for *UNICORN 6+* result exports, it handles the complex nested ZIP structures and binary data unpacking internally—eliminating the need for external UNICORN licenses or manual exporting from the workstation.

This tool is ideal for researchers who need to standardize their data visualization for lab notebooks, presentations, and high-impact publications.

---

## Features

* **Intuitive GUI**: A professional interface with progress tracking and real-time logging.
* **Deep ZIP Parsing**: Automatically handles nested internal data structures to find UV, Conductivity, Pressure, and pH curves.
* **Intelligent Fraction Filtering**:
* Uses strict numeric filtering (`isdigit`) to keep plots clean.
* Automatically hides system labels like "Waste", "Inject", or "Out 1".


* **Publication-Ready Exports**:
* Supports **PNG, JPG, PDF, and TIFF**.
* Customizable resolution with a dedicated **DPI (Dots Per Inch)** selector (up to 1200 DPI).


* **Advanced Axis Control**:
* Set manual X (Volume) and Y (Intensity) limits.
* Optional **0–100% Normalization** for easier run-to-run comparison.
* Automatic multi-axis scaling for diverse signal types.


* **Standalone Windows Integration**: Includes a custom taskbar icon fix for seamless Windows desktop use.

---

## Requirements

* **Python 3.8+**
* `PyQt5` (For the interface)
* `matplotlib` (For high-quality rendering)
* `xmltodict` (For data parsing)

---

## Setup

1. **Clone or Download**: Save the script and your `icon.ico` file to a local directory.
2. **Install Dependencies**:
```bash
pip install PyQt5 matplotlib xmltodict

```



---

## Usage

### Running the Script

Launch the application via your terminal:

```bash
python akta_plotter_pro.py

```

### Workflow

1. **Load Data**: Click **Add Files** or **Add Folder** to select your UNICORN `.zip` exports.
2. **Scan**: Use the blue **Scan for Curves** button to detect available signals in your files.
3. **Configure**: Select your primary curve (e.g., UV 280) and secondary curves (e.g., Cond, Fractions).
4. **Export**: Set your desired DPI and output folder, then click **Generate Plots**.

### Compiling to a Standalone Executable (.exe)

To create a single Windows application file that includes the custom icon:

```bash
python -m PyInstaller --onefile --windowed --icon="icon.ico" --add-data "icon.ico;." --hidden-import="matplotlib.backends.backend_svg" --hidden-import="matplotlib.backends.backend_pdf" --hidden-import="matplotlib.backends.backend_agg" --name "AKTA_Plotter" akta_plotter_gui.py
```

---

## License

This project is open-source and available under the [MIT License](https://www.google.com/search?q=LICENSE).

---

## Acknowledgments

* Binary unpacking logic inspired by the `pycorn` project.
* Built using the Matplotlib and PyQt5 frameworks.
