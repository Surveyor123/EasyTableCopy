# EasyTableCopy

**EasyTableCopy** is an NVDA add-on designed to solve a common frustration: copying tables from the Web or lists from Windows into documents (like Word, Excel, or Outlook) without losing formatting, borders, or structure.

## 1. Key Features

* **Dual Copy Engine:** Choose between "Standard" mode for best visual fidelity or "Reconstructed" mode for guaranteed structure integrity.
* **Smart Selection:** Easily select non-adjacent rows or specific columns to copy.
* **Desktop & Explorer Support:** Instantly convert File Explorer lists or application views into copyable tables. Copy specific columns or combinations of columns.
* **Cell-Level Copying:** Quickly copy individual cell content without the surrounding table structure.
* **Table Statistics:** Get instant information about table dimensions (row and column count) anywhere.
* **Audio Feedback:** Distinct sounds and speech messages keep you informed about the copying process.

## 2. Web Mode (Browsers)

This feature works in Browse Mode within web browsers (Chrome, Edge, Firefox, etc.).

### A. The Copy Menu

Navigate inside any table on a website and press `NVDA + Alt + T` to open the action menu.

* **Copy Table (Standard):**
Uses the browser's native copy function.
*Pros:* Preserves exact fonts, background colors, and links.
*Cons:* Relies on the browser; empty cells might collapse in some target applications.

* **Copy Table (Reconstructed):**
The "Safe Mode." The add-on ignores the browser and manually rebuilds the table from scratch.
*Pros:* **Guarantees** that empty cells are filled (preserving borders) and enforces grid lines.
*Cons:* May lose complex CSS styling (like rounded corners).

* **Copy Current Row:** Copies only the row where your cursor is located (Standard mode).
* **Copy Current Column:** Manually extracts and copies the vertical column where your cursor is located.

### B. Smart Selection (Marking)

You can select specific items to copy in a batch. **Note:** You can mark Rows OR Columns, but not both simultaneously.

#### How to Copy Specific Rows:

1. Navigate to a row you want to copy.
2. Press `Control + Alt + Space`. NVDA will confirm: "Row Marked."
3. Move to another row and repeat.
4. Open the menu (`NVDA + Alt + T`) and select **"Copy Marked"**.

#### How to Copy Specific Columns:

1. Navigate to a cell within the column you want.
2. Press `Control + Alt + Shift + Space`. NVDA will confirm: "Column Marked."
3. Repeat for other columns.
4. Open the menu and select **"Copy Marked"**.

> **Note:** To clear your selections, press `Control + Alt + Windows + Space` or use the "Clear Selections" option in the menu.

### C. Additional Web Features

* **Copy Marked Rows as Text:** After marking rows, you can copy them as plain text without table structure using the `Copy Marked as Text` command (no default key, assign in Input Gestures).
* **Copy Current Cell:** Quickly copy the content of the current cell using the `Copy Current Cell` command.

## 3. Desktop & Explorer Mode (Windows)

EasyTableCopy also works in File Explorer and standard list views in various applications.

### A. Quick List Copy

1. Focus on a list (e.g., a folder with files).
2. Press `NVDA + Alt + T`.
3. **Result:** The entire list is converted into a structured table (with headers like Name, Date, Type) and copied to your clipboard.

### B. Column-Specific Copying (Desktop & Explorer Only)

You can copy individual columns or combinations of columns from any desktop list or Explorer view. These commands only work in desktop contexts (not in web browsers).

| Command | Description |
| --- | --- |
| Copy Column 1 | Copies the first column (usually Name) |
| Copy Column 2 | Copies the second column (usually Size or Type) |
| Copy Column 3 | Copies the third column (usually Date Modified) |
| Copy Columns 1-2 | Copies the first and second columns together |
| Copy Columns 1-3 | Copies the first, second, and third columns together |
| Copy Columns 1 and 3 | Copies the first and third columns (skipping the second) |

**How to use:**
1. Focus on any list or Explorer window.
2. Press the key you've assigned to the desired column command (no default keys - assign in Input Gestures).
3. The selected columns will be copied as a table with headers.

### C. Table Statistics in Desktop Mode

Press the `Table Statistics` command (no default key) to hear:
- Number of items in the folder/list
- Number of columns displayed

## 4. Universal Features (Work Everywhere)

### A. Table Statistics

Use the `Table Statistics` command anywhere (web, desktop, Explorer) to get instant information about the current table or list:
- Number of rows/items
- Number of columns

The add-on intelligently samples large tables to provide quick and accurate information without performance lag.

### B. Copy Current Cell

Use the `Copy Current Cell` command anywhere to quickly copy just the content of the current cell without the surrounding table structure. Perfect for:
- Copying specific values from web tables
- Extracting single items from lists
- Quick data entry tasks

## 5. Shortcuts Cheat Sheet

*(You can customize all shortcuts in NVDA Menu -> Preferences -> Input Gestures -> EasyTableCopy)*

### Default Shortcuts

| Shortcut | Function | Context |
| --- | --- | --- |
| `NVDA + Alt + T` | Open Menu (Web) / Copy List (Desktop) | Everywhere |
| `Ctrl + Alt + Space` | Mark/Unmark Row | Web Only |
| `Ctrl + Alt + Shift + Space` | Mark/Unmark Column | Web Only |
| `Ctrl + Alt + Win + Space` | Clear All Selections | Web Only |

### No Default Shortcuts (Assign Your Own)

These commands have no default key assignments. To use them, assign your own shortcuts in NVDA's Input Gestures dialog:

| Command | Description | Context |
| --- | --- | --- |
| Copy Column 1 | Copy first column | Desktop/Explorer Only |
| Copy Column 2 | Copy second column | Desktop/Explorer Only |
| Copy Column 3 | Copy third column | Desktop/Explorer Only |
| Copy Columns 1-2 | Copy first and second columns | Desktop/Explorer Only |
| Copy Columns 1-3 | Copy first three columns | Desktop/Explorer Only |
| Copy Columns 1 and 3 | Copy first and third columns | Desktop/Explorer Only |
| Table Statistics | Announce table dimensions | Everywhere |
| Copy Current Cell | Copy current cell content | Everywhere |
| Copy Marked as Text | Copy marked rows as plain text | Web Only |

## 6. Important Notes

* **Excel/Calc Protection:** The add-on automatically disables itself in Excel and similar applications to prevent conflicts with native copy functions.
* **Selection Limitations:** You cannot mix row and column selections. Choose either rows OR columns, but not both.
* **Large Tables:** The add-on handles large tables efficiently. For very large web tables, statistics are calculated using sampling for optimal performance.
* **Web vs Desktop:** Some commands are context-specific (web-only or desktop-only) to ensure reliable operation. Commands that don't apply in the current context are simply ignored.

## 7. Feedback and Contributions

If you encounter any issues or have suggestions for improvement, please visit the add-on's repository or contact the author.