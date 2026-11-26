# -*- coding: utf-8 -*-
"""Xuất Word: chức năng + thao tác + trường dữ liệu theo từng tài khoản."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(FRONTEND))

try:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx", "-q"])
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

from export_functions_excel import (
    ACTIVITY,
    DATA_ENTITIES,
    DEPT_LABELS,
    HANDOFF,
    menu_path,
)
from main import get_db
from ops_modules import IMPORT_BULK_ENTITIES, OPS_MODULES
from rbac import MENU_ITEMS
from seed_org import get_user_access, seed_departments_and_users
from workflow_links import DEPT_APPLICATION_ACTIONS

OUT = ROOT / "nghiepvu" / "Danh_sach_chuc_nang_theo_nguoi_dung.docx"

NAVY = RGBColor(0x00, 0x52, 0x8C)
MUTATE_HINTS = (
    "thêm",
    "tạo",
    "gửi",
    "import",
    "assign",
    "create",
    "add",
    "đồng bộ",
    "bàn giao",
    "mở điểm",
    "qr",
    "enroll",
    "copy",
    "notify",
    "hand-",
    "sync",
)


def _set_run_font(run, *, name="Times New Roman", size=11, bold=False, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _shade_cell(cell, hex_color: str) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def _set_cell_border(cell) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "B0B0B0")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def _cell_text(cell, text: str, *, bold=False, size=9, color=None, center=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text or "")
    _set_run_font(run, size=size, bold=bold, color=color)
    _set_cell_border(cell)
    cell.vertical_alignment = 1  # center


def _action_label(item) -> str:
    if isinstance(item, dict):
        return str(item.get("label") or item.get("id") or "").strip()
    return str(item or "").strip()


def _ops_for_module(code: str, cfg: dict | None, *, exec_view: bool) -> list[str]:
    ops: list[str] = []
    if not cfg:
        ops.append("Mở chức năng (không có bảng danh sách ops)")
        if exec_view:
            ops.append("Chỉ xem / in / xuất Excel (Giám đốc / Trợ lý)")
        return ops

    mode = cfg.get("mode") or "view"
    if exec_view:
        ops.append("Chỉ xem (không thêm/sửa/xóa)")
        ops.append("In danh sách")
        ops.append("Xuất Excel")
        for b in cfg.get("row_buttons") or []:
            bid = str(b.get("id") or "")
            if bid.startswith("view_") or bid in (
                "open_eval",
                "view_evals",
                "view_courses",
                "view_students",
                "view_program",
                "preview_round_doc",
                "download_round_doc",
            ):
                lab = _action_label(b)
                if lab:
                    ops.append(lab)
        if cfg.get("search"):
            ops.append("Tìm kiếm")
        return _uniq(ops)

    if mode == "view":
        ops.append("Xem danh sách")
    else:
        ops.append("Quản lý (xem + thao tác)")

    pa = cfg.get("primary_action")
    if pa:
        ops.append("Thao tác chính: " + _action_label(pa))

    for a in cfg.get("actions") or []:
        lab = _action_label(a)
        if lab:
            ops.append(lab)

    for b in cfg.get("row_buttons") or []:
        lab = _action_label(b)
        if lab:
            ops.append("Dòng: " + lab)

    rea = cfg.get("row_edit_action")
    if rea:
        ops.append("Dòng: " + _action_label(rea))

    if cfg.get("allow_delete"):
        ops.append("Xóa (xác nhận trước; chặn nếu đã có dữ liệu khâu sau)")
    if cfg.get("import_bulk") or code in IMPORT_BULK_ENTITIES:
        ops.append("Import Excel (bắt buộc CCCD với hồ sơ người; trùng CCCD thì cập nhật)")
        ops.append("Tải mẫu Excel")
        ops.append("Xóa hàng loạt đã chọn")
    if cfg.get("search"):
        ops.append("Tìm kiếm")
    if cfg.get("status_filter"):
        ops.append("Lọc trạng thái")
    if cfg.get("program_filter"):
        ops.append("Lọc chương trình")
    if cfg.get("round_filter"):
        ops.append("Lọc đợt tuyển sinh")
    if cfg.get("fee_actions"):
        ops.append("Xác nhận nộp phí / minh chứng")
    if cfg.get("charge_actions"):
        ops.append("Ghi nhận thanh toán / miễn giảm")
    return _uniq(ops)


def _fields_for_module(code: str, cfg: dict | None) -> str:
    bits: list[str] = []
    if cfg:
        for col in cfg.get("columns") or []:
            if isinstance(col, (tuple, list)) and len(col) >= 2:
                bits.append(str(col[1]))
            elif isinstance(col, dict):
                bits.append(str(col.get("label") or col.get("key") or ""))
            else:
                bits.append(str(col))
    extra = DATA_ENTITIES.get(code) or ""
    if extra:
        bits.append("Nguồn: " + extra)
    return "; ".join(x for x in bits if x).strip() or "—"


def _uniq(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in items:
        k = x.strip()
        if not k or k.lower() in seen:
            continue
        seen.add(k.lower())
        out.append(k)
    return out


def _is_exec(user: dict) -> bool:
    if user.get("is_admin"):
        return False
    codes = {d.get("code") for d in (user.get("departments") or [])}
    if codes & {"admin_he_thong", "it"}:
        return False
    return bool(codes & {"ban_giam_doc", "tro_ly_bgd"})


def _workflow_ops(user: dict, code: str) -> list[str]:
    if code != "admissions.applications":
        return []
    if _is_exec(user):
        return []
    depts = {d.get("code") for d in (user.get("departments") or [])}
    labels = []
    for d in depts:
        for a in DEPT_APPLICATION_ACTIONS.get(d) or []:
            labels.append(f"Hồ sơ: {a.get('label')} → {a.get('status')}")
    return _uniq(labels)


def load_users():
    with get_db() as conn:
        seed_departments_and_users(conn)
        cur = conn.cursor()
        users = []
        for r in cur.execute(
            "SELECT u.id, u.email, u.name, u.is_admin "
            "FROM user u WHERE u.email NOT LIKE '%@%' ORDER BY u.email"
        ):
            acc = get_user_access(conn, r[0])
            users.append(
                {
                    "id": r[0],
                    "login": r[1],
                    "name": r[2],
                    "is_admin": bool(r[3]),
                    "departments": acc["departments"],
                    "scopes": acc["program_scopes"],
                    "perms": list(acc["permission_codes"] or []),
                    "lang": acc.get("lang", "vi"),
                }
            )
    return users


def _perm_set(user: dict) -> set[str]:
    if user.get("is_admin"):
        return {m["code"] for m in MENU_ITEMS}
    return set(user.get("perms") or [])


def add_heading(doc: Document, text: str, level: int) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = NAVY
        run.font.name = "Times New Roman"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")


def set_narrow_margins(section) -> None:
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Cm(29.7)
    section.page_height = Cm(21.0)
    section.left_margin = Cm(1.4)
    section.right_margin = Cm(1.4)
    section.top_margin = Cm(1.4)
    section.bottom_margin = Cm(1.4)


def style_table_header(row) -> None:
    for cell in row.cells:
        _shade_cell(cell, "00528C")
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.bold = True
                run.font.size = Pt(9)
                run.font.name = "Times New Roman"
                run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")


def add_user_table(doc: Document, user: dict, menu_by_code: dict) -> int:
    exec_view = _is_exec(user)
    perms = _perm_set(user)
    items = [m for m in sorted(MENU_ITEMS, key=lambda x: (x.get("sort") or 0, x["code"])) if m["code"] in perms]
    if not items:
        doc.add_paragraph("Tài khoản chưa được gán chức năng menu.")
        return 0

    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    hdr = table.rows[0].cells
    labels = ["STT", "Chức năng", "Menu", "Khả năng thao tác", "Trường dữ liệu hiện có", "Mô tả"]
    for i, lab in enumerate(labels):
        _cell_text(hdr[i], lab, bold=True, size=9, color=RGBColor(0xFF, 0xFF, 0xFF), center=True)
    style_table_header(table.rows[0])

    widths = (Cm(1.2), Cm(4.2), Cm(4.0), Cm(6.4), Cm(6.4), Cm(4.6))
    for row in table.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = w

    for i, m in enumerate(items, start=1):
        code = m["code"]
        cfg = OPS_MODULES.get(code)
        ops = _ops_for_module(code, cfg, exec_view=exec_view)
        ops.extend(_workflow_ops(user, code))
        if m.get("nav") is False:
            ops.insert(0, "Quyền nền (không hiện mục menu riêng)")
        row = table.add_row().cells
        _cell_text(row[0], str(i), size=8, center=True)
        _cell_text(row[1], m.get("label") or code, size=9, bold=True)
        _cell_text(row[2], menu_path(m), size=8)
        _cell_text(row[3], "; ".join(ops) if ops else "—", size=8)
        _cell_text(row[4], _fields_for_module(code, cfg), size=8)
        _cell_text(row[5], ACTIVITY.get(code) or m.get("workflow") or HANDOFF.get(code) or "", size=8)
        if i % 2 == 0:
            for c in row:
                _shade_cell(c, "F4F8FB")
    return len(items)


def main() -> None:
    users = load_users()
    menu_by_code = {m["code"]: m for m in MENU_ITEMS}

    doc = Document()
    styles = doc.styles["Normal"]
    styles.font.name = "Times New Roman"
    styles.font.size = Pt(11)
    styles._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    set_narrow_margins(doc.sections[0])

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("SMARTUNI / CFVG")
    _set_run_font(r, size=14, bold=True, color=NAVY)

    t2 = doc.add_paragraph()
    t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t2.add_run("Danh sách chức năng theo đối tượng người dùng")
    _set_run_font(r, size=18, bold=True, color=NAVY)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run(
        f"Ngày xuất: {date.today().isoformat()}  ·  "
        f"{len(MENU_ITEMS)} chức năng menu  ·  {len(users)} tài khoản"
    )
    _set_run_font(r, size=11, color=RGBColor(0x44, 0x44, 0x44))

    note = doc.add_paragraph()
    r = note.add_run(
        "Tài liệu gom quyền thực tế trên hệ thống (sau seed RBAC): với mỗi tài khoản liệt kê "
        "chức năng được phép, khả năng thao tác trên giao diện (xem/thêm/sửa/xóa/import/in/xuất, "
        "nút dòng, lọc), và trường dữ liệu đang hiển thị trên danh sách. "
        "Giám đốc / Trợ lý BGD: xem + in + xuất Excel, không thêm/sửa/xóa. "
        "Xóa luôn yêu cầu xác nhận và bị chặn nếu đã có dữ liệu khâu sau. "
        "Import hồ sơ người yêu cầu CCCD; trùng CCCD thì cập nhật xuyên suốt Hồ sơ → Thí sinh → Người học."
    )
    _set_run_font(r, size=11)

    add_heading(doc, "1. Mục lục tài khoản", 1)
    toc = doc.add_table(rows=1, cols=5)
    for i, lab in enumerate(["STT", "Đăng nhập", "Họ tên / vai trò", "Bộ phận", "Số chức năng"]):
        _cell_text(toc.rows[0].cells[i], lab, bold=True, size=9, color=RGBColor(0xFF, 0xFF, 0xFF), center=True)
    style_table_header(toc.rows[0])
    for i, u in enumerate(users, start=1):
        depts = "; ".join(
            DEPT_LABELS.get(d.get("code"), d.get("name") or d.get("code")) for d in u["departments"]
        ) or "—"
        row = toc.add_row().cells
        _cell_text(row[0], str(i), size=9, center=True)
        _cell_text(row[1], u["login"], size=9, bold=True)
        _cell_text(row[2], u["name"], size=9)
        _cell_text(row[3], depts, size=8)
        _cell_text(row[4], str(len(_perm_set(u))), size=9, center=True)

    add_heading(doc, "2. Danh mục chức năng hệ thống", 1)
    p = doc.add_paragraph()
    r = p.add_run("Toàn bộ mã chức năng đang khai báo trên menu, kèm nhóm và mô tả.")
    _set_run_font(r, size=11)

    cat = doc.add_table(rows=1, cols=5)
    for i, lab in enumerate(["STT", "Chức năng", "Mã", "Menu", "Mô tả"]):
        _cell_text(cat.rows[0].cells[i], lab, bold=True, size=9, color=RGBColor(0xFF, 0xFF, 0xFF), center=True)
    style_table_header(cat.rows[0])
    for i, m in enumerate(sorted(MENU_ITEMS, key=lambda x: (x.get("sort") or 0, x["code"])), start=1):
        row = cat.add_row().cells
        _cell_text(row[0], str(i), size=8, center=True)
        _cell_text(row[1], m.get("label") or m["code"], size=9, bold=True)
        _cell_text(row[2], m["code"], size=8)
        _cell_text(row[3], menu_path(m), size=8)
        _cell_text(row[4], ACTIVITY.get(m["code"]) or m.get("workflow") or "", size=8)
        if i % 2 == 0:
            for c in row:
                _shade_cell(c, "F4F8FB")

    add_heading(doc, "3. Chi tiết theo đối tượng người dùng", 1)
    for idx, u in enumerate(users, start=1):
        depts = "; ".join(
            DEPT_LABELS.get(d.get("code"), d.get("name") or d.get("code")) for d in u["departments"]
        ) or "—"
        scopes = ", ".join(u.get("scopes") or []) or "—"
        role = "Super Admin (toàn quyền)" if u.get("is_admin") else (
            "Xem báo cáo / dữ liệu (không sửa)" if _is_exec(u) else "Thao tác theo quyền được gán"
        )
        add_heading(doc, f"3.{idx}. {u['name']}  ({u['login']})", 2)
        info = doc.add_paragraph()
        r = info.add_run(
            f"Đăng nhập: {u['login']}    ·    Bộ phận: {depts}    ·    "
            f"Phạm vi chương trình: {scopes}    ·    Vai trò thao tác: {role}    ·    "
            f"Số chức năng: {len(_perm_set(u))}"
        )
        _set_run_font(r, size=11, bold=True, color=NAVY)
        add_user_table(doc, u, menu_by_code)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Wrote {OUT}")
    print(f"Users={len(users)} Functions={len(MENU_ITEMS)}")


if __name__ == "__main__":
    main()
