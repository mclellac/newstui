# News TUI

A simple, terminal-based news reader.

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

### News Sources

The application can be configured to use different news sources. The default news source is CBC News. You can change the news source by adding a `source` key to your `config.json` file. The available sources are `cbc` and `rss`.

#### CBC

By default, the `cbc` source will display all available sections. You can customize the list of sections by adding a `sections` key to the `cbc` source configuration.

Here is an example `config.json` file that uses the `cbc` source with a custom list of sections:

```json
{
    "theme": "dracula",
    "source": "cbc",
    "sources": {
        "cbc": {
            "sections": [
                "News",
                "Sports",
                "Canada",
                "World",
                "Toronto",
                "British Columbia",
                "Comedy"
            ]
        }
    }
}
```

#### RSS

To use an RSS feed as your news source, you need to configure the `rss` source in your `config.json` file. The `rss` source takes a `feeds` dictionary, where the keys are the names of the feeds and the values are the URLs of the feeds.

Here is an example `config.json` file that uses the `rss` source with two feeds:

```json
{
    "theme": "dracula",
    "source": "rss",
    "sources": {
        "rss": {
            "feeds": {
                "Hacker News": "https://news.ycombinator.com/rss",
                "Lobsters": "https://lobste.rs/rss"
            }
        }
    }
}
```

### Meta Sections

You can create "meta" sections that combine stories from multiple other sections. To do this, add a `meta_sections` key to your `config.json` file. The value should be a dictionary where the keys are the names of your meta sections and the values are lists of the sections to include.

Here is an example `config.json` that defines a "My Feed" meta section that combines stories from the "Hacker News" RSS feed and the "World" and "Sports" sections from CBC:

```json
{
    "theme": "dracula",
    "source": "rss",
    "sources": {
        "cbc": {
            "sections": [
                "World",
                "Sports"
            ]
        },
        "rss": {
            "feeds": {
                "Hacker News": "https://news.ycombinator.com/rss"
            }
        }
    },
    "meta_sections": {
        "My Feed": [
            "Hacker News",
            "World",
            "Sports"
        ]
    }
}
```