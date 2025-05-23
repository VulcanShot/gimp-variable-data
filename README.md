# Variable Data for GIMP

This plug-in allows for batch editing and exporting of images using variable data sets, with similar functionality to Photoshop. A CSV file is used to retrieve the properties to change for each iteration.

## Supported Properties

- Foreground color (or font color)
- Background color
- Visibility
- Text

## CSV Format

- Row 1: Names of the target layers (or paths)
- Row 2: Properties to modify (foreground, background, visible, or text)
- Row 3+: Data entries for each batch iteration

> Example: [colors.csv](./test/colors.csv)

## Notes

- Layers precede homonimous paths
- There must at least one drawable layer i.e not text layer to fill paths

## Installation

1. In GIMP navigate to:

    ```Edit > Preferences > Folders (left pane) > Plug-Ins```

2. Open the directory where user plugins can be found and copy the `variable-data` directory there.
3. Change the permissions of the script (Windows/macOS):

    ```sh
        $ chmod +x variable_data.py
    ```

4. Restart GIMP.

## Usage

> File > Create > Variable Data...
