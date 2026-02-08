# -*- coding: utf-8 -*-
# EasyTableCopy v2026.2.1
# Author: Çağrı Doğan

import globalPluginHandler
import addonHandler
import api
import ui
import textInfos
import controlTypes
import wx
import winUser
from comtypes.client import CreateObject
import ctypes
import keyboardHandler
import re
import time
import winsound

# Çeviri sistemini başlat
addonHandler.initTranslation()
user32 = ctypes.windll.user32

# --- YASAKLI UYGULAMALAR (Excel Koruması) ---
BLOCKED_APPS = ["excel", "calc", "soffice"]

# --- DECORATOR ---
def script_description(desc):
    def wrapper(func):
        func.__doc__ = desc
        return func
    return wrapper

def safe_str(val):
    if val is None: return ""
    return str(val)

def color_to_hex(col_val):
    if col_val is None: return None
    try:
        if hasattr(col_val, 'red'):
            return "#%02x%02x%02x" % (col_val.red, col_val.green, col_val.blue)
        if isinstance(col_val, int):
            r = col_val & 0xFF
            g = (col_val >> 8) & 0xFF
            b = (col_val >> 16) & 0xFF
            return "#%02x%02x%02x" % (r, g, b)
    except: pass
    return None

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("EasyTableCopy")

    # --- ROL TANIMLARI (GÜNCELLENDİ: WhatsApp İçin GROUPING Eklendi) ---
    TABLE_ROLES = set()
    ROW_ROLES = set()
    CELL_ROLES = set()
    CONTENT_ROLES = set()
    r = controlTypes.Role
    
    role_map = {
        "TABLE_ROLES": ["TABLE", "GRID", "LISTGRID", "LIST", "TREEVIEW"],
        # WhatsApp öğeleri genelde GROUPING olarak görünür, buraya ekledik:
        "ROW_ROLES": ["TABLEROW", "ROW", "LISTITEM", "TREEVIEWITEM", "GROUPING"],
        "CELL_ROLES": ["TABLECELL", "TABLECOLUMNHEADER", "TABLEROWHEADER", "CELL", "GRIDCELL"],
        "CONTENT_ROLES": ["STATICTEXT", "EDITABLETEXT", "TABLECELL", "GRIDCELL", "TEXT", "PARAGRAPH", "LINK", "GROUPING"]
    }

    for target_set, names in role_map.items():
        s = locals()[target_set]
        for name in names:
            if hasattr(r, name): s.add(getattr(r, name))

    marked_rows = [] 
    marked_col_indices = set() 

    # --- HELPERS ---
    def get_context_tree_interceptor(self):
        obj = api.getFocusObject()
        if hasattr(obj, "treeInterceptor") and obj.treeInterceptor:
            return obj.treeInterceptor
        return None

    def find_object_by_role(self, start_obj, target_roles):
        obj = start_obj
        for _loop in range(50): 
            if not obj: break
            if obj.role in target_roles: return obj
            obj = obj.parent
        return None

    def get_column_index(self, cell_obj):
        parent = cell_obj.parent
        if parent:
            try:
                siblings = [c for c in parent.children if c.role in self.CELL_ROLES]
                if cell_obj in siblings: return siblings.index(cell_obj)
            except: pass
        try:
            if hasattr(cell_obj, "columnNumber"):
                val = cell_obj.columnNumber
                if val > 0: return val - 1
        except: pass
        return -1

    def _restore_focus(self, hwnd):
        try:
            if hwnd:
                if winUser.getForegroundWindow() != hwnd:
                    winUser.setForegroundWindow(hwnd)
                winUser.setFocus(hwnd)
                time.sleep(0.05) 
        except: pass

    # =========================================================================
    # ENGINE A: NATIVE COPY
    # =========================================================================
    def perform_native_copy(self, obj, label, original_hwnd):
        try:
            self._restore_focus(original_hwnd)
            
            count_info = ""
            if obj.role in self.TABLE_ROLES:
                c = len([child for child in obj.children if child.role in self.ROW_ROLES])
                if c == 1: count_info = _(" (1 row)")
                elif c > 1: count_info = _(" ({count} rows)").format(count=c)
            elif obj.role in self.ROW_ROLES:
                c = len([child for child in obj.children if child.role in self.CELL_ROLES])
                if c == 1: count_info = _(" (1 cell)")
                elif c > 1: count_info = _(" ({count} cells)").format(count=c)

            info = obj.makeTextInfo(textInfos.POSITION_ALL)
            info.updateSelection()
            
            winsound.Beep(440, 100) 
            keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
            
            wx.CallLater(300, self._retry_clipboard_repair, label, count_info, 1)
        except Exception:
            ui.message(_("Selection failed."))

    def _retry_clipboard_repair(self, label, count_info, attempt):
        if not wx.TheClipboard.Open():
            if attempt < 15:
                wx.CallLater(200, self._retry_clipboard_repair, label, count_info, attempt + 1)
                return
            else:
                ui.message(_("{label} copied{count} (Raw).").format(label=label, count=count_info))
                return

        try:
            if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_HTML)):
                data_obj = wx.HTMLDataObject()
                if wx.TheClipboard.GetData(data_obj):
                    raw_html = data_obj.GetHTML()
                    modified = False
                    
                    cell_pattern = re.compile(r'(<td\b[^>]*>)([\s\r\n]*(?:<br\s*/?>)?[\s\r\n]*)(</td>)', re.IGNORECASE)
                    if cell_pattern.search(raw_html):
                        raw_html = cell_pattern.sub(r'\1&nbsp;\3', raw_html)
                        modified = True
                    
                    if "border=" not in raw_html.lower() and "border:" not in raw_html.lower():
                         table_pattern = re.compile(r'(<table\b[^>]*)(>)', re.IGNORECASE)
                         raw_html = table_pattern.sub(r'\1 border="1" cellspacing="0" cellpadding="5"\2', raw_html)
                         modified = True

                    if modified:
                        new_data = wx.DataObjectComposite()
                        new_html_obj = wx.HTMLDataObject()
                        new_html_obj.SetHTML(raw_html)
                        new_data.Add(new_html_obj, True)
                        
                        text_obj = wx.TextDataObject()
                        if wx.TheClipboard.GetData(text_obj):
                            new_data.Add(text_obj, False)
                        
                        wx.TheClipboard.SetData(new_data)
                        winsound.Beep(880, 100)
                        ui.message(_("{label} copied{count}.").format(label=label, count=count_info))
                    else:
                        winsound.Beep(600, 100)
                        ui.message(_("{label} copied{count}.").format(label=label, count=count_info))
            else:
                ui.message(_("{label} copied{count} (Text).").format(label=label, count=count_info))
        except:
            ui.message(_("Error."))
        finally:
            wx.TheClipboard.Close()

    # =========================================================================
    # ENGINE B: HYBRID MANUAL
    # =========================================================================
    def get_hybrid_html(self, obj):
        content = ""
        txt = ""
        if obj.childCount > 0:
            parts = [self.get_hybrid_html(c) for c in obj.children]
            content = " ".join([p[0] for p in parts])
            txt = " ".join([p[1] for p in parts])
        else:
            raw = (obj.name or obj.value or "").strip()
            txt = raw
            content = raw.replace("&", "&amp;").replace("<", "&lt;")

        if not txt and obj.childCount == 0: return "", ""

        try:
            info = obj.makeTextInfo(textInfos.POSITION_ALL)
            fmt = info.getFormatFieldAtStart()
            
            if fmt.get('bold'): content = f"<b>{content}</b>"
            if fmt.get('italic'): content = f"<i>{content}</i>"
            if fmt.get('underline'): content = f"<u>{content}</u>"
            
            css = []
            fa = []
            fg = color_to_hex(fmt.get('color'))
            if fg: 
                css.append(f"color:{fg}")
                fa.append(f'color="{fg}"')
            font = fmt.get('font-name')
            if font:
                clean = safe_str(font).replace("'", "").replace('"', "")
                css.append(f"font-family:'{clean}',sans-serif")
                fa.append(f'face="{clean}"')
            if css:
                s = ";".join(css)
                content = f'<span style="{s}">{content}</span>'
            if fa:
                f_str = " ".join(fa)
                content = f'<font {f_str}>{content}</font>'
        except: pass

        if obj.role == controlTypes.Role.LINK:
            url = getattr(obj, 'value', '#')
            content = f'<a href="{url}">{content}</a>'
        return content, txt

    def copy_manual_safe(self, html, text):
        if not wx.TheClipboard.Open(): return False
        try:
            d = wx.DataObjectComposite()
            h = wx.HTMLDataObject()
            full = "<html><head><meta charset='utf-8'></head><body>" + html + "</body></html>"
            h.SetHTML(full)
            d.Add(h, True)
            t = wx.TextDataObject(text)
            d.Add(t, False)
            return wx.TheClipboard.SetData(d)
        except: return False
        finally: wx.TheClipboard.Close()

    def perform_full_table_manual(self, current_obj, original_hwnd):
        table = self.find_object_by_role(current_obj, self.TABLE_ROLES)
        if not table:
            ui.message(_("Table not found."))
            return

        winsound.Beep(440, 100)
        wx.CallLater(10, ui.message, _("Scanning table..."))

        all_rows = []
        def flatten(o):
            for c in o.children:
                if c.role in self.ROW_ROLES: all_rows.append(c)
                elif c.childCount > 0 and c.role not in self.CELL_ROLES: flatten(c)
        flatten(table)

        if not all_rows:
            ui.message(_("Table is empty."))
            return

        html_out = ["<table border='1' style='border-collapse:collapse'>"]
        text_out = []

        for row in all_rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells: cells = list(row.children)
            r_html = "<tr>"
            r_txt = []
            for c in cells:
                bg_style = ""
                try:
                    bg = color_to_hex(c.makeTextInfo(textInfos.POSITION_ALL).getFormatFieldAtStart().get('background-color'))
                    if bg: bg_style = f' bgcolor="{bg}"'
                except: pass

                h, t = self.get_hybrid_html(c)
                if not h.strip(): h = "&nbsp;"
                if not t.strip(): t = " "
                r_html += f"<td{bg_style} style='padding:5px'>{h}</td>"
                r_txt.append(t)
            r_html += "</tr>"
            html_out.append(r_html)
            text_out.append("\t".join(r_txt))
        
        html_out.append("</table>")
        
        if self.copy_manual_safe("".join(html_out), "\n".join(text_out)):
            self._restore_focus(original_hwnd)
            winsound.Beep(880, 100)
            count = len(all_rows)
            msg = ""
            if count == 1: msg = _("Table copied (1 row) [Reconstructed].")
            else: msg = _("Table copied ({count} rows) [Reconstructed].").format(count=count)
            wx.CallLater(100, ui.message, msg)
        else:
            ui.message(_("Copy failed."))

    def perform_marked_copy_manual(self, original_hwnd):
        target_rows = []
        target_col_indices = self.marked_col_indices
        
        if self.marked_rows:
            if len(self.marked_rows) > 0:
                ti = self.get_context_tree_interceptor()
                try:
                    obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                    table = self.find_object_by_role(obj, self.TABLE_ROLES)
                    if not table and self.marked_rows: 
                        table = self.find_object_by_role(self.marked_rows[0], self.TABLE_ROLES)
                    if table:
                        def flatten(o):
                            for c in o.children:
                                if c.role in self.ROW_ROLES:
                                    if c in self.marked_rows: target_rows.append(c)
                                elif c.childCount > 0 and c.role not in self.CELL_ROLES: flatten(c)
                        flatten(table)
                    else: target_rows = self.marked_rows
                except: target_rows = self.marked_rows
        
        elif self.marked_col_indices:
            ti = self.get_context_tree_interceptor()
            try:
                obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
                table = self.find_object_by_role(obj, self.TABLE_ROLES)
                def flatten_all(o):
                    for c in o.children:
                        if c.role in self.ROW_ROLES: target_rows.append(c)
                        elif c.childCount > 0 and c.role not in self.CELL_ROLES: flatten_all(c)
                flatten_all(table)
                target_col_indices = sorted(list(self.marked_col_indices))
            except: return

        if not target_rows:
            self._restore_focus(original_hwnd)
            ui.message(_("Error: No items to copy."))
            return

        winsound.Beep(440, 100)
        html_out = ["<table border='1' style='border-collapse:collapse'>"]
        text_out = []

        for row in target_rows:
            cells = [c for c in row.children if c.role in self.CELL_ROLES]
            if not cells: cells = list(row.children)
            r_html = "<tr>"
            r_txt = []
            indices = target_col_indices if target_col_indices else range(len(cells))
            for idx in indices:
                h, t = "", ""
                bg_style = ""
                if 0 <= idx < len(cells):
                    c = cells[idx]
                    try:
                        bg = color_to_hex(c.makeTextInfo(textInfos.POSITION_ALL).getFormatFieldAtStart().get('background-color'))
                        if bg: bg_style = f' bgcolor="{bg}"'
                    except: pass
                    h, t = self.get_hybrid_html(c)
                if not h.strip(): h = "&nbsp;"
                if not t.strip(): t = " "
                r_html += f"<td{bg_style} style='padding:5px'>{h}</td>"
                r_txt.append(t)
            r_html += "</tr>"
            html_out.append(r_html)
            text_out.append("\t".join(r_txt))
        
        html_out.append("</table>")
        
        if self.copy_manual_safe("".join(html_out), "\n".join(text_out)):
            self._restore_focus(original_hwnd)
            winsound.Beep(880, 100)
            msg = ""
            if self.marked_rows:
                c = len(target_rows)
                if c == 1: msg = _("Copied 1 row.")
                else: msg = _("Copied {count} rows.").format(count=c)
            else:
                c = len(target_col_indices)
                if c == 1: msg = _("Copied 1 column.")
                else: msg = _("Copied {count} columns.").format(count=c)
            ui.message(msg)
            self.marked_rows = []
            self.marked_col_indices.clear()
        else:
            self._restore_focus(original_hwnd)
            ui.message(_("Copy failed."))

    # =========================================================================
    # ENGINE C: DESKTOP LISTS (IsChild - Stable)
    # =========================================================================
    def copy_explorer_content(self, hwnd):
        try:
            shell = CreateObject("shell.application")
            folder_view = None
            for window in shell.Windows():
                try: 
                    # Eski Yöntem (Kullanıcı Tercihi)
                    if window.hwnd == hwnd or user32.IsChild(window.hwnd, hwnd):
                        folder_view = window.Document
                        break
                except: continue
            
            if not folder_view: return False
            
            items = folder_view.Folder.Items()
            count = items.Count
            
            if count == 0:
                ui.message(_("Folder is empty."))
                return True
            
            # COM bağlantısı başarılıysa bip
            winsound.Beep(440, 100)
            
            headers = [folder_view.Folder.GetDetailsOf(None, i) for i in range(15) if folder_view.Folder.GetDetailsOf(None, i)]
            text_rows = []
            html_rows = ["<table border='1'><tr>" + "".join([f"<td><b>{h}</b></td>" for h in headers]) + "</tr>"]
            text_rows.append("\t".join(headers))
            for i in range(count):
                item = items.Item(i)
                vals = [str(folder_view.Folder.GetDetailsOf(item, idx)).strip() for idx in range(len(headers))]
                html_rows.append("<tr>" + "".join([f"<td>{v if v else '&nbsp;'}</td>" for v in vals]) + "</tr>")
                text_rows.append("\t".join(vals))
            html_rows.append("</table>")
            
            self.copy_manual_safe("".join(html_rows), "\n".join(text_rows))
            winsound.Beep(880, 100)
            
            if count == 1: ui.message(_("Folder copied (1 item)."))
            else: ui.message(_("Folder copied ({count} items).").format(count=count))
            return True
        except: return False

    def perform_list_view_copy_fallback(self, list_obj):
        # WHATSAPP FIX: Try/Except bloğu ve Else durumu eklendi.
        try:
            items = [c for c in list_obj.children if c.role in self.ROW_ROLES]
            count = len(items)
            
            if count == 0:
                ui.message(_("No items found."))
                return
            
            # Veri bulundu, bip çal.
            winsound.Beep(440, 100)
            
            text_rows = []
            html_rows = ["<table border='1'>"]
            
            extracted_any = False

            for item in items:
                cols = [c for c in item.children if c.role in self.CONTENT_ROLES] or [item]
                r_html = "<tr>"
                r_txt = []
                for col in cols:
                    h, t = self.get_hybrid_html(col)
                    if t.strip(): extracted_any = True
                    if not h.strip(): h = "&nbsp;"
                    r_html += f"<td style='padding:5px'>{h}</td>"
                    r_txt.append(t)
                r_html += "</tr>"
                html_rows.append(r_html)
                text_rows.append("\t".join(r_txt))
            html_rows.append("</table>")
            
            if not extracted_any:
                ui.message(_("No accessible text found."))
                return

            if self.copy_manual_safe("".join(html_rows), "\n".join(text_rows)):
                winsound.Beep(880, 100)
                if count == 1: ui.message(_("List copied (1 item)."))
                else: ui.message(_("List copied ({count} items).").format(count=count))
            else:
                # SESSİZLİK ÇÖZÜMÜ: Eğer pano hatası olursa artık sessiz kalmayacak.
                ui.message(_("Clipboard error. Try again."))
        except Exception:
            ui.message(_("Error processing list."))

    # =========================================================================
    # MENÜ & GİRDİLER
    # =========================================================================
    def on_menu_select(self, item_id, current_obj, original_hwnd):
        if item_id == 1: # Standard (Native)
            target = self.find_object_by_role(current_obj, self.TABLE_ROLES)
            if target: self.perform_native_copy(target, _("Table"), original_hwnd)
            else: ui.message(_("Target not found."))
        elif item_id == 2: # Current Row
            target = self.find_object_by_role(current_obj, self.ROW_ROLES)
            if target: self.perform_native_copy(target, _("Row"), original_hwnd)
            else: ui.message(_("Target not found."))
        elif item_id == 3: # Reconstructed (Safe)
            self.perform_full_table_manual(current_obj, original_hwnd)
        elif item_id == 4: # Current Column
            target = self.find_object_by_role(current_obj, self.CELL_ROLES)
            if target:
                idx = self.get_column_index(target)
                if idx != -1:
                    self.marked_col_indices.add(idx)
                    self.perform_marked_copy_manual(original_hwnd)
                    self.marked_col_indices.discard(idx)
        elif item_id == 5: # Marked
            self.perform_marked_copy_manual(original_hwnd)
        elif item_id == 6:
            if not self.marked_rows and not self.marked_col_indices:
                ui.message(_("No selection to clear."))
            else:
                self.marked_rows = []
                self.marked_col_indices.clear()
                ui.message(_("Selections cleared."))

    def show_phantom_menu(self, current_obj, original_hwnd):
        dummy_frame = wx.Frame(None, -1, "Helper", pos=(0,0), size=(1,1))
        dummy_frame.Show()
        dummy_frame.Raise() 
        dummy_frame.SetFocus()
        try: winUser.setForegroundWindow(dummy_frame.GetHandle())
        except: pass

        menu = wx.Menu()
        menu.Append(1, _("Copy Table (Standard)"))
        menu.Append(2, _("Copy Current Row"))
        menu.Append(3, _("Copy Table (Reconstructed)"))
        menu.Append(4, _("Copy Current Column"))
        
        if self.marked_rows or self.marked_col_indices:
            count = len(self.marked_rows) if self.marked_rows else len(self.marked_col_indices)
            lbl = ""
            if self.marked_rows:
                lbl = _("rows") if count > 1 else _("row")
            else:
                lbl = _("columns") if count > 1 else _("column")
            menu.Append(5, _("Copy Marked ({count} {lbl})").format(count=count, lbl=lbl))
            menu.Append(6, _("Clear Selections"))
        menu.Append(wx.ID_CANCEL, _("Cancel"))
        
        def _cmd(evt):
            id = evt.GetId()
            dummy_frame.Destroy()
            wx.CallLater(10, self.on_menu_select, id, current_obj, original_hwnd)
        
        menu.Bind(wx.EVT_MENU, _cmd)
        dummy_frame.PopupMenu(menu)
        if dummy_frame:
            try: dummy_frame.Destroy()
            except: pass
            self._restore_focus(original_hwnd)

    # --- KISAYOLLAR ---

    @script_description(_("Opens Copy Menu (Web) or Copies List (Desktop)."))
    def script_tableMenu(self, gesture):
        # 1. EXCEL KORUMASI
        focus = api.getFocusObject()
        if focus.appModule:
            app_name = focus.appModule.appName.lower()
            for blocked in BLOCKED_APPS:
                if blocked in app_name:
                    ui.message(_("Use standard copy (Ctrl+C) in this application."))
                    return

        ti = self.get_context_tree_interceptor()
        # Web
        if ti:
            try: obj = ti.makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
            except: obj = api.getFocusObject()
            if self.find_object_by_role(obj, self.TABLE_ROLES):
                hwnd = winUser.getForegroundWindow()
                wx.CallLater(10, self.show_phantom_menu, obj, hwnd)
            else:
                ui.message(_("Not on a table."))
        # Desktop
        else:
            if self.copy_explorer_content(focus.windowHandle): return
            target_list = None
            if focus.role in self.TABLE_ROLES: target_list = focus
            else:
                temp = focus
                for _loop in range(5):
                    if not temp: break
                    if temp.role in self.TABLE_ROLES:
                        target_list = temp
                        break
                    temp = temp.parent
            if target_list:
                self.perform_list_view_copy_fallback(target_list)
            else:
                ui.message(_("Focus is not on a list or table."))

    @script_description(_("Marks/Unmarks current row."))
    def script_markRow(self, gesture):
        if not self.get_context_tree_interceptor(): 
            gesture.send()
            return
        if self.marked_col_indices:
            ui.message(_("Cannot mark rows while columns are selected."))
            return
        obj = None
        try: obj = self.get_context_tree_interceptor().makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except: pass
        row = self.find_object_by_role(obj, self.ROW_ROLES)
        if row:
            if row in self.marked_rows:
                self.marked_rows.remove(row)
                c = len(self.marked_rows)
                if c == 0: ui.message(_("Row Unmarked."))
                elif c == 1: ui.message(_("Row Unmarked. Total: 1 row"))
                else: ui.message(_("Row Unmarked. Total: {count} rows").format(count=c))
            else:
                self.marked_rows.append(row)
                c = len(self.marked_rows)
                if c == 1: ui.message(_("Row Marked. Total: 1 row"))
                else: ui.message(_("Row Marked. Total: {count} rows").format(count=c))
        else: ui.message(_("Not a row."))

    @script_description(_("Marks/Unmarks current column."))
    def script_markColumn(self, gesture):
        if not self.get_context_tree_interceptor(): 
            gesture.send()
            return
        if self.marked_rows:
            ui.message(_("Cannot mark columns while rows are selected."))
            return
        obj = None
        try: obj = self.get_context_tree_interceptor().makeTextInfo(textInfos.POSITION_CARET).NVDAObjectAtStart
        except: pass
        cell = self.find_object_by_role(obj, self.CELL_ROLES)
        if cell:
            idx = self.get_column_index(cell)
            if idx != -1:
                if idx in self.marked_col_indices:
                    self.marked_col_indices.remove(idx)
                    c = len(self.marked_col_indices)
                    if c == 0: ui.message(_("Column Unmarked."))
                    elif c == 1: ui.message(_("Column Unmarked. Total: 1 column"))
                    else: ui.message(_("Column Unmarked. Total: {count} columns").format(count=c))
                else:
                    self.marked_col_indices.add(idx)
                    c = len(self.marked_col_indices)
                    if c == 1: ui.message(_("Column Marked. Total: 1 column"))
                    else: ui.message(_("Column Marked. Total: {count} columns").format(count=c))
            else: ui.message(_("Index error."))
        else: ui.message(_("Not a cell."))

    @script_description(_("Clears selections."))
    def script_clearAll(self, gesture):
        if not self.get_context_tree_interceptor(): 
            gesture.send()
            return
        if not self.marked_rows and not self.marked_col_indices:
            ui.message(_("No selection to clear."))
            return
        self.marked_rows = []
        self.marked_col_indices.clear()
        ui.message(_("Selections cleared."))

    __gestures = {
        "kb:alt+nvda+t": "tableMenu",
        "kb:control+alt+space": "markRow",
        "kb:control+alt+shift+space": "markColumn",
        "kb:control+alt+windows+space": "clearAll"
    }