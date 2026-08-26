# tom-select (vendored)

[Tom Select](https://tom-select.js.org) v2.6.2, Apache-2.0, vendored so the
registration questionnaire's searchable dropdowns need no CDN and no
JavaScript build step.

Files are copied verbatim from the npm package `tom-select@2.6.2`:

| Vendored file                    | Source in the npm package                     |
| -------------------------------- | --------------------------------------------- |
| `tom-select.complete.min.js`     | `dist/js/tom-select.complete.min.js`          |
| `tom-select.bootstrap5.min.css`  | `dist/css/tom-select.bootstrap5.min.css`      |
| `LICENSE`                        | `LICENSE`                                     |

To update, `npm pack tom-select@<version>`, unpack it, copy those files over,
and bump the version in this file.
