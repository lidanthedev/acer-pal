# base.html

This is the base HTML file for the web application. It sets up the basic structure of the web pages and includes the necessary CSS and JavaScript files.

## Structure

The file is structured as follows:

- The `<!doctype html>` declaration defines the document type and version of HTML.
- The `<html>` element is the root element of an HTML page.
- The `<head>` element contains meta-information about the HTML document.
- The `<body>` element contains the content of the HTML document.

## Meta Tags

- The `<meta charset="utf-8">` tag sets the character encoding for the HTML document.
- The `<meta name="viewport" content="width=device-width, initial-scale=1">` tag sets the viewport to scale for mobile devices.

## Scripts and Stylesheets

- jQuery and Bootstrap are included via CDN links in the `<head>` section.
- A custom CSS file (`base.css`) is included via the Flask `url_for` function.

## Blocks

- The `{% block title %}{% endblock %}` is a placeholder for the title of the page.
- The `{% block content %}{% endblock %}` is a placeholder for the main content of the page.

## Includes

- The `{% include 'socket.io.html' %}` line includes the HTML for socket.io functionality.
- The `{% include 'navbar.html' %}` line includes the HTML for the navigation bar.
- The `{% include 'loading.html' %}` line includes the HTML for a loading screen.

## Theme

- The `data-bs-theme="dark"` attribute sets the Bootstrap theme to dark.