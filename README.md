# Illustrator like Variable Data for GIMP

# Introduction

Upload a CSV file with columns representing colors. The plugin will generate individual pdf files, save each of those in specific folder with specific name, then group all those files in new pdf file for printing.

## CSV column headings

- The name of the text layer to apply the color
- The name of the path to fill with the color

## CSV format notes

- First column is always path to **PDF** file to save the generated image!
- GIMP image must have at least one drawable layer i.e not text layer. The top most drawbale layer is where the rectangle backgrounds will be drawn.

# Installation

1. In GIMP navigate to:

    ```Edit > Preferences > Folders (left pane) > Plug-Ins```

2. Open the directory user plugins can be found tThen copy variable_data.py to that directory.
3. Change to executable:

    ```$ chmod +x variable_data.py```

4. Restart GIMP.
