# News TUI

A simple, terminal-based news reader for the CBC News website.

## Installation

To install the application, you can use `pip` to install it directly from this repository:

```bash
pip install .
```

This will install the `newstui` command-line tool.

## Usage

Once installed, you can run the application with the following command:

```bash
newstui
```

### Options

-   `--theme <themename>`: Temporarily use a different theme.
-   `--debug`: Enable debug logging to a file in `/tmp/`.

## Configuration

The application can be configured via a `config.json` file located at `~/.config/news/config.json`.

### Themes

The application supports custom themes. A selection of themes is provided in the `config/news/themes` directory of this repository.

To use a theme, you must first copy the theme files to your user configuration directory:

```bash
mkdir -p ~/.config/news/themes
cp -r config/news/themes/* ~/.config/news/themes/
```

Then, you can specify the theme to use in your `config.json` file. For example, to use the `dracula` theme, your `~/.config/news/config.json` should look like this:

```json
{
    "theme": "dracula"
}
```

This will load the `dracula.css` theme file from your `~/.config/news/themes` directory.

### CBC Sections

By default, the application will display all available sections from the CBC News website. You can customize the list of sections by adding a `sections` key to the `cbc` source configuration.

### Meta Sections

You can create "meta" sections that combine stories from multiple other sections. To do this, add a `meta_sections` key to your `config.json` file. The value should be a dictionary where the keys are the names of your meta sections and the values are lists of the sections to include.

### Example Configuration

Here is an example `config.json` file that defines a custom list of CBC sections and a "My Feed" meta section that combines stories from the "World" and "Sports" sections:

```json
{
    "theme": "dracula",
    "sources": {
        "cbc": {
            "sections": [
                "World",
                "Sports",
                "Canada",
                "Toronto"
            ]
        }
    },
    "meta_sections": {
        "My Feed": [
            "World",
            "Sports"
        ]
    }
}
```