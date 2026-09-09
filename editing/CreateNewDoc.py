"""
Class-based rebuild of "Basic_Tamplate.docx" (the Unit Outline template)
using python-docx.

Instead of running top-to-bottom as a script, this now exposes a
`UnitOutline` class. You create an instance, use its methods to fill in
whatever sections you want (everything starts blank, just like the
original template), then call `.save(path)` to generate the .docx.

Example
-------
    outline = UnitOutline()

    outline.set_unit_description("This unit introduces students to ...")

    # Learning outcomes start with just ONE (LO1), empty. Add more as needed:
    outline.set_learning_outcome(0, "Explain core programming concepts.")
    outline.add_learning_outcome("Apply object-oriented design principles.")
    outline.add_learning_outcome("Work effectively in a team environment.")

    outline.save("Unit_Outline_COMP101.docx")

Every section has a matching setter -- see the method list below the
class definition, or just read the docstrings.
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

NAVY = RGBColor(0x1F, 0x38, 0x64)
WHITE = "#FFFFFF"
HEADER_BAR = "D9D9D9"
GREY_TEXT = RGBColor(0x00, 0x00, 0x00)

FULL_WIDTH_TWIPS = 9350

# ---------------------------------------------------------------------------
# Low level helpers (borders, shading, column widths -- python-docx does not
# expose these natively, so we manipulate the underlying XML directly).
# These stay as plain module-level functions since they don't depend on any
# per-document state -- they just act on whatever cell/table/paragraph is
# passed in.
# ---------------------------------------------------------------------------


def set_cell_border(cell, color="999999", sz=4):
    """Add a thin border on all four sides of a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tcPr.append(borders)
    return cell


def set_cell_shading(cell, fill_hex):
    """Set the background fill color of a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)
    return cell


def set_col_widths(table, widths_twips):
    """Force explicit column widths (both on <tblGrid> and on every cell)."""
    table.autofit = False
    tbl = table._tbl
    tblGrid = tbl.find(qn("w:tblGrid"))
    if tblGrid is None:
        tblGrid = OxmlElement("w:tblGrid")
        tbl.insert(0, tblGrid)
    for child in list(tblGrid):
        tblGrid.remove(child)
    for w in widths_twips:
        gridCol = OxmlElement("w:gridCol")
        gridCol.set(qn("w:w"), str(w))
        tblGrid.append(gridCol)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            if idx < len(widths_twips):
                cell.width = Twips(widths_twips[idx])
                tcPr = cell._tc.get_or_add_tcPr()
                tcW = tcPr.find(qn("w:tcW"))
                if tcW is None:
                    tcW = OxmlElement("w:tcW")
                    tcPr.append(tcW)
                tcW.set(qn("w:type"), "dxa")
                tcW.set(qn("w:w"), str(widths_twips[idx]))
    return table


def set_run(run, text=None, bold=False, italic=False, size=12, color=None,
            underline=False, font_name="Segoe UI Semibold"):
    """Apply text and basic formatting (bold, italic, size, color) to a run."""
    if text is not None:
        run.text = text
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = font_name
    if color is not None:
        run.font.color.rgb = color if isinstance(color, RGBColor) else RGBColor.from_string(color)
    run.underline = underline
    return run


def add_paragraph(cell_or_doc, text="", bold=False, italic=False, size=12,
                   color=None, align=None, bullet=False, space_before=0,
                   space_after=6):
    """Add a new paragraph (optionally bulleted) to a cell or to the document."""
    p = cell_or_doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if bullet:
        p.style = "List Bullet"
    if text:
        run = p.add_run()
        set_run(run, text, bold=bold, italic=italic, size=size, color=color)
    return p


def header_bar_row(table, text):
    """Insert a full-width title bar (merged row) at the bottom of a table."""
    row = table.add_row()
    first_cell = row.cells[0]
    for c in row.cells[1:]:
        first_cell = first_cell.merge(c)
    set_cell_shading(first_cell, HEADER_BAR)
    for c in row.cells:
        set_cell_border(c)
    first_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = first_cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run(run, color=RGBColor(0x00, 0x00, 0x00))
    return row


def label_value_row(table, label, value=""):
    """Add a row with a right-aligned label on the left and a value field on the right."""
    row = table.add_row()
    lcell, vcell = row.cells[0], row.cells[1]
    set_cell_shading(lcell, WHITE)
    for c in row.cells:
        set_cell_border(c)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    lp = lcell.paragraphs[0]
    lp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_run(lp.add_run(label), bold=False, size=12, font_name="Segoe UI Semibold")
    if value:
        vp = vcell.paragraphs[0]
        set_run(vp.add_run(value), size=10)
    return row


def checkbox_cell(cell, label, checked=False):
    """Write a checkbox glyph (checked or unchecked) followed by a label into a cell."""
    set_cell_border(cell)
    p = cell.paragraphs[0]
    box = "\u2611 " if checked else "\u2610 "
    set_run(p.add_run(box + label), bold=False, size=10, font_name="Segoe UI Symbol")
    return cell


def empty_box(title, target_doc, extra_paragraphs=None):
    """Create a one-column table: a title bar plus a content cell.

    The content cell is empty by default, or filled with fixed paragraphs
    passed in `extra_paragraphs` (a list of kwargs dicts for add_paragraph).
    """
    table = target_doc.add_table(rows=0, cols=1)
    header_bar_row(table, title)
    row = table.add_row()
    cell = row.cells[0]
    set_cell_border(cell)
    cell.paragraphs[0].text = ""
    if extra_paragraphs:
        for kwargs in extra_paragraphs:
            add_paragraph(cell, **kwargs)
        if cell.paragraphs[0].text == "" and len(cell.paragraphs) > 1:
            cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)
    set_col_widths(table, [FULL_WIDTH_TWIPS])
    target_doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return table


def add_hyperlink(paragraph, url, text, color="0563C1", underline=True):
    """Insert a real clickable hyperlink run into an existing paragraph."""
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    color_el = OxmlElement("w:color")
    color_el.set(qn("w:val"), color)
    rPr.append(color_el)

    if underline:
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rPr.append(u)

    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "20")
    rPr.append(sz)

    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def lo_row(table, code, text=""):
    """Add a Learning Outcomes row: a bold code cell (e.g. 'LO1') plus a description cell."""
    row = table.add_row()
    ccell, dcell = row.cells
    set_cell_border(ccell)
    set_cell_border(dcell)
    ccell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    set_run(ccell.paragraphs[0].add_run(code), bold=True, size=10)
    dcell.paragraphs[0].text = ""
    if text:
        set_run(dcell.paragraphs[0].add_run(text), size=10)
    return row


def at_row(table, no, description="", due="", weight="", los=""):
    """Add a single Assessment Tasks row, numbered in the first column."""
    row = table.add_row()
    for c in row.cells:
        set_cell_border(c)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run(row.cells[0].paragraphs[0].add_run(str(no)), size=9)
    for cell, value in zip(row.cells[1:], (description, due, weight, los)):
        cell.paragraphs[0].text = ""
        if value:
            set_run(cell.paragraphs[0].add_run(value), size=9)
    return row


def policy_item(cell, title, url, desc, first=False):
    """Add one policy entry (bold title, hyperlink, bulleted description) to a cell."""
    p = cell.paragraphs[0] if first else cell.add_paragraph()
    p.paragraph_format.space_before = Pt(0 if first else 8)
    p.paragraph_format.space_after = Pt(2)
    set_run(p.add_run(title), bold=True, size=10)
    add_paragraph(cell, "", size=10, space_after=2)
    plink = cell.paragraphs[-1]
    add_hyperlink(plink, url, url)
    bp = add_paragraph(cell, "", size=10, bullet=True, space_after=6)
    set_run(bp.add_run(desc), size=10)
    return p


# ---------------------------------------------------------------------------
# The document class
# ---------------------------------------------------------------------------


class UnitOutline:
    """Builder for an SPI Unit Outline .docx document.

    Create an instance, call the `set_...` / `add_...` methods for whichever
    sections you want to fill in (anything you don't touch stays blank, just
    like the original template), then call `.save(path)`.

    The actual python-docx `Document` is only assembled when you call
    `.build()` or `.save()` -- so you can set content in any order beforehand.
    """

    #: Week labels used in the Weekly Activities table, in order.
    WEEK_LABELS = [f"Week {n}" for n in range(1, 10)] + ["Week 10+11"]

    #: Delivery mode checkbox labels, grouped by row (row3 has a blank 3rd cell).
    DELIVERY_MODE_ROWS = [
        ["Face to face on site", "Online/E-Learning", "Intensive"],
        ["Work-Integrated Learning", "Mixed/Blended", None],
        ["Full-Time", "Part-time", None],
    ]

    def __init__(self, logo_path="Logo_SPI.png", n_assessment_rows=5):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.logo_path = (
            logo_path if os.path.isabs(logo_path) else os.path.join(script_dir, logo_path)
        )

        # --- Basic information -------------------------------------------------
        self.basic_info = {
            "Unit Code:": "",
            "Unit Name:": "",
            "Associated Award:": "",
            "Unit Type:": "",
            "Credit Points:": "",
        }

        # --- Student workload ----------------------------------------------------
        self.workload = {
            "Timetabled Study:": "",
            "Personal Study:": "",
            "Total Study:": "",
        }

        # --- Delivery mode(s) -- which checkboxes are ticked --------------------
        self.delivery_modes_checked = set()

        # --- Pre-requisites --------------------------------------------------
        self.prerequisites = {
            "Pre-requisites:": "",
            "Assumed Knowledge:": "",
            "Specialist Equipment:": "",
        }

        # --- Free-text sections ------------------------------------------------
        self.unit_description = ""
        self.assessment_summary = ""
        self.response_to_student_feedback = ""
        self.prescribed_texts = ""
        self.suggested_readings = ""

        # --- Learning outcomes -- starts with just ONE (LO1), empty ------------
        self.learning_outcomes = [""]

        # --- Assessment tasks -- starts with `n_assessment_rows` blank rows ----
        self.assessment_tasks = [
            {"description": "", "due": "", "weight": "", "los": ""}
            for _ in range(n_assessment_rows)
        ]

        # --- Weekly activities ---------------------------------------------------
        self.weekly_activities = {label: "" for label in self.WEEK_LABELS}

    # ------------------------------------------------------------------
    # Basic information / workload / delivery mode / pre-requisites
    # ------------------------------------------------------------------
    def set_basic_info(self, **fields):
        """Set any of: unit_code, unit_name, associated_award, unit_type, credit_points."""
        mapping = {
            "unit_code": "Unit Code:",
            "unit_name": "Unit Name:",
            "associated_award": "Associated Award:",
            "unit_type": "Unit Type:",
            "credit_points": "Credit Points:",
        }
        for key, value in fields.items():
            if key not in mapping:
                raise ValueError(f"Unknown basic_info field: {key!r}")
            self.basic_info[mapping[key]] = value
        return self

    def set_workload(self, timetabled=None, personal=None, total=None):
        if timetabled is not None:
            self.workload["Timetabled Study:"] = timetabled
        if personal is not None:
            self.workload["Personal Study:"] = personal
        if total is not None:
            self.workload["Total Study:"] = total
        return self

    def set_delivery_mode(self, label, checked=True):
        """Tick/untick a delivery mode checkbox, e.g. 'Face to face on site'."""
        valid = {lbl for row in self.DELIVERY_MODE_ROWS for lbl in row if lbl}
        if label not in valid:
            raise ValueError(f"Unknown delivery mode: {label!r}. Valid options: {sorted(valid)}")
        if checked:
            self.delivery_modes_checked.add(label)
        else:
            self.delivery_modes_checked.discard(label)
        return self

    def set_prerequisites(self, prerequisites=None, assumed_knowledge=None, specialist_equipment=None):
        if prerequisites is not None:
            self.prerequisites["Pre-requisites:"] = prerequisites
        if assumed_knowledge is not None:
            self.prerequisites["Assumed Knowledge:"] = assumed_knowledge
        if specialist_equipment is not None:
            self.prerequisites["Specialist Equipment:"] = specialist_equipment
        return self

    # ------------------------------------------------------------------
    # Simple free-text sections
    # ------------------------------------------------------------------
    def set_unit_description(self, text):
        self.unit_description = text
        return self

    def set_assessment_summary(self, text):
        self.assessment_summary = text
        return self

    def set_response_to_student_feedback(self, text):
        self.response_to_student_feedback = text
        return self

    def set_prescribed_texts(self, text):
        self.prescribed_texts = text
        return self

    def set_suggested_readings(self, text):
        self.suggested_readings = text
        return self

    # ------------------------------------------------------------------
    # Learning outcomes -- starts with one (LO1), add more as needed
    # ------------------------------------------------------------------
    def add_learning_outcome(self, text=""):
        """Append a new learning outcome (LO2, LO3, ...). Returns its index."""
        self.learning_outcomes.append(text)
        return len(self.learning_outcomes) - 1

    def set_learning_outcome(self, index, text):
        """Set/overwrite the text of an existing learning outcome by index (0 = LO1)."""
        self.learning_outcomes[index] = text
        return self

    # ------------------------------------------------------------------
    # Assessment tasks -- starts with a few blank rows, add more as needed
    # ------------------------------------------------------------------
    def add_assessment_task(self, description="", due="", weight="", los=""):
        """Append a new Assessment Tasks row. Returns its index."""
        self.assessment_tasks.append(
            {"description": description, "due": due, "weight": weight, "los": los}
        )
        return len(self.assessment_tasks) - 1

    def set_assessment_task(self, index, description=None, due=None, weight=None, los=None):
        """Update fields of an existing Assessment Tasks row by index."""
        row = self.assessment_tasks[index]
        if description is not None:
            row["description"] = description
        if due is not None:
            row["due"] = due
        if weight is not None:
            row["weight"] = weight
        if los is not None:
            row["los"] = los
        return self

    # ------------------------------------------------------------------
    # Weekly activities
    # ------------------------------------------------------------------
    def set_week(self, week, text):
        """Set the content for a week, e.g. set_week(1, "...") or set_week("Week 10+11", "...")."""
        label = f"Week {week}" if isinstance(week, int) else week
        if label not in self.weekly_activities:
            raise ValueError(f"Unknown week label: {label!r}. Valid options: {self.WEEK_LABELS}")
        self.weekly_activities[label] = text
        return self

    # ------------------------------------------------------------------
    # Build / save
    # ------------------------------------------------------------------
    def build(self):
        """Assemble and return a python-docx `Document` from the current content."""
        doc = Document()

        section = doc.sections[0]
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.top_margin = Cm(1.76)
        section.bottom_margin = Cm(1.76)
        section.left_margin = Cm(1.76)
        section.right_margin = Cm(1.76)

        self._build_header(doc)
        self._build_basic_info(doc)
        self._build_workload(doc)
        self._build_delivery_modes(doc)
        self._build_prerequisites(doc)

        empty_box("Unit Description", doc, extra_paragraphs=(
            [{"text": self.unit_description, "size": 10}] if self.unit_description else None
        ))

        self._build_learning_outcomes(doc)
        self._build_assessment_tasks(doc)

        empty_box("Assessment Summary", doc, extra_paragraphs=(
            [{"text": self.assessment_summary, "size": 10}] if self.assessment_summary else None
        ))

        self._build_weekly_activities(doc)

        empty_box("Response to Student Feedback", doc, extra_paragraphs=(
            [{"text": self.response_to_student_feedback, "size": 10}]
            if self.response_to_student_feedback else None
        ))

        self._build_policies(doc)
        self._build_ai_tools(doc)

        empty_box("Prescribed Texts", doc, extra_paragraphs=(
            [{"text": self.prescribed_texts, "size": 10}] if self.prescribed_texts else None
        ))

        empty_box("Suggested Readings and Resources", doc, extra_paragraphs=(
            [{"text": self.suggested_readings, "size": 10}] if self.suggested_readings else None
        ))

        return doc

    def save(self, path):
        """Build the document and save it to `path`. Returns the path."""
        doc = self.build()
        doc.save(path)
        print(f"Document created successfully: {path}")
        return path

    # ------------------------------------------------------------------
    # Internal section builders
    # ------------------------------------------------------------------
    def _build_header(self, doc):
        header_table = doc.add_table(rows=1, cols=2)
        header_table.autofit = False
        logo_cell, text_cell = header_table.rows[0].cells

        for c in header_table.rows[0].cells:
            set_cell_border(c, color="FFFFFF", sz=0)
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        logo_cell.paragraphs[0].text = ""
        if os.path.isfile(self.logo_path):
            run = logo_cell.paragraphs[0].add_run()
            run.add_picture(self.logo_path, height=Cm(1.8))

        text_cell.paragraphs[0].text = ""
        p1 = text_cell.paragraphs[0]
        set_run(p1.add_run("Sydney Polytechnic Institute"), bold=True, size=16, color=NAVY)
        p1.paragraph_format.space_after = Pt(0)

        p2 = text_cell.add_paragraph()
        set_run(p2.add_run("Unit Outline"), italic=True, size=13, color=NAVY)
        p2.paragraph_format.space_after = Pt(0)

        set_col_widths(header_table, [1400, 7950])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_basic_info(self, doc):
        basic_table = doc.add_table(rows=0, cols=2)
        for label, value in self.basic_info.items():
            label_value_row(basic_table, label, value)
        set_col_widths(basic_table, [3000, 6350])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_workload(self, doc):
        workload_table = doc.add_table(rows=0, cols=3)
        header_bar_row(workload_table, "Student Workload (hours per week)")
        row = workload_table.add_row()
        for cell, (label, value) in zip(row.cells, self.workload.items()):
            set_cell_border(cell)
            text = f"{label} {value}".strip() if value else label
            set_run(cell.paragraphs[0].add_run(text), bold=False, size=12, font_name="Segoe UI Semibold")
        set_col_widths(workload_table, [3117, 3117, 3116])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_delivery_modes(self, doc):
        delivery_table = doc.add_table(rows=0, cols=3)
        header_bar_row(delivery_table, "Delivery Mode(s)")
        for row_labels in self.DELIVERY_MODE_ROWS:
            row = delivery_table.add_row()
            for cell, label in zip(row.cells, row_labels):
                if label is None:
                    set_cell_border(cell)
                else:
                    checkbox_cell(cell, label, checked=label in self.delivery_modes_checked)
        set_col_widths(delivery_table, [3117, 3117, 3116])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_prerequisites(self, doc):
        prereq_table = doc.add_table(rows=0, cols=2)
        for label, value in self.prerequisites.items():
            label_value_row(prereq_table, label, value)
        set_col_widths(prereq_table, [3000, 6350])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_learning_outcomes(self, doc):
        lo_table = doc.add_table(rows=0, cols=2)
        header_bar_row(lo_table, "Learning Outcomes")
        for i, text in enumerate(self.learning_outcomes, start=1):
            lo_row(lo_table, f"LO{i}", text)
        set_col_widths(lo_table, [1200, 8150])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_assessment_tasks(self, doc):
        at_table = doc.add_table(rows=0, cols=5)
        header_bar_row(at_table, "Assessment Tasks")

        row = at_table.add_row()
        headers = ["No.", "Type & Description", "Due", "Weight", "LO's"]
        for cell, text in zip(row.cells, headers):
            set_cell_border(cell)
            set_cell_shading(cell, HEADER_BAR)
            cell.paragraphs[0].alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if text != "Type & Description" else WD_ALIGN_PARAGRAPH.LEFT
            )
            set_run(cell.paragraphs[0].add_run(text), bold=False, size=12, font_name="Segoe UI Semibold")

        for i, task in enumerate(self.assessment_tasks, start=1):
            at_row(at_table, i, task["description"], task["due"], task["weight"], task["los"])

        set_col_widths(at_table, [700, 5200, 1500, 1100, 850])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_weekly_activities(self, doc):
        weekly_table = doc.add_table(rows=0, cols=2)
        header_bar_row(weekly_table, "Weekly Activities")
        for label in self.WEEK_LABELS:
            row = weekly_table.add_row()
            lcell, ccell = row.cells
            set_cell_border(lcell)
            set_cell_border(ccell)
            lcell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_run(lcell.paragraphs[0].add_run(label), size=10)
            ccell.paragraphs[0].text = ""
            text = self.weekly_activities[label]
            if text:
                set_run(ccell.paragraphs[0].add_run(text), size=10)
        set_col_widths(weekly_table, [1400, 7950])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_policies(self, doc):
        """Links to Policies -- fixed institutional content, same for every outline."""
        policy_table = doc.add_table(rows=0, cols=1)
        header_bar_row(policy_table, "Links to Policies")
        row = policy_table.add_row()
        cell = row.cells[0]
        set_cell_border(cell)
        cell.paragraphs[0].text = ""

        policy_item(cell, "Student Progression, Exclusion & Graduation Policy",
            "https://spi.nsw.edu.au/wp-content/uploads/2023/04/SPI-Student-Progression-Exclusion-and-Graduation-Policy.pdf",
            "includes important information about attendance requirements, academic performance & interventions.",
            first=True)

        policy_item(cell, "Student Assessment Policy & Procedures",
            "https://spi.nsw.edu.au/wp-content/uploads/2023/11/22.A-SPI-Student-Assessment-Policy-and-Procedure-Version-2.0.pdf",
            "includes information about assessment practices, grading, special consideration (i.e., what to do if you miss an assessment task for a valid reason).")

        policy_item(cell, "Academic Integrity Policy & Procedures",
            "https://spi.nsw.edu.au/wp-content/uploads/2023/04/SPI-Academic-Integrity-Policy-and-Procedure.pdf",
            "includes information about good academic practice, academic misconduct, plagiarism and cheating.")

        policy_item(cell, "Graduate Attributes Policy",
            "https://spi.nsw.edu.au/wp-content/uploads/2023/04/SPI-Graduate-Attributes-Policy.pdf",
            "outlines the graduate attributes that your course learning outcomes are contributing to.")

        set_col_widths(policy_table, [FULL_WIDTH_TWIPS])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _build_ai_tools(self, doc):
        """Use of AI Tools -- fixed institutional content, same for every outline."""
        ai_table = doc.add_table(rows=0, cols=1)
        header_bar_row(ai_table, "Use of AI Tools")
        row = ai_table.add_row()
        cell = row.cells[0]
        set_cell_border(cell)
        cell.paragraphs[0].text = ""

        add_paragraph(cell,
            "ChatGPT and other generative AI tools have the capacity to greatly "
            "enhance your higher education experience if used responsibly. Learning "
            "how to use AI tools to co-create is an important skill that is in "
            "demand by many industry sectors. The following website has many good "
            "resources for students to understand the valuable role that AI tools "
            "can play in your education experience:",
            size=10, space_after=6)

        p = cell.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        add_hyperlink(p,
            "https://www.teqsa.gov.au/guides-resources/higher-education-good-practice-hub/artificial-intelligence/gen-ai-student-resources-and-support",
            "https://www.teqsa.gov.au/guides-resources/higher-education-good-practice-hub/artificial-intelligence/gen-ai-student-resources-and-support")

        add_paragraph(cell,
            "Be sure to check each assessment task to see if AI tools are permitted "
            "for that task (and if so, in what form) or if they are not permitted.",
            size=10, space_after=0)

        if cell.paragraphs[0].text == "" and len(cell.paragraphs) > 1:
            cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)

        set_col_widths(ai_table, [FULL_WIDTH_TWIPS])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)


# ---------------------------------------------------------------------------
# Example usage -- only runs if you execute this file directly.
# Edit/delete freely; import the class elsewhere instead if you prefer.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))

    outline = UnitOutline()

    outline.set_basic_info(
        unit_code="COMP101",
        unit_name="Introduction to Programming",
        associated_award="Bachelor of Computing",
        unit_type="Core",
        credit_points="10",
    )

    outline.set_unit_description(
        "This unit introduces students to fundamental programming concepts "
        "including variables, control flow, functions, and basic data structures."
    )

    # Learning outcomes start with just LO1 -- add more only if you need them.
    outline.set_learning_outcome(0, "Explain fundamental programming concepts.")
    outline.add_learning_outcome("Design and implement simple algorithms.")
    outline.add_learning_outcome("Debug and test small programs.")

    outline.add_assessment_task("Weekly quizzes", "Ongoing", "20%", "LO1")
    outline.add_assessment_task("Programming assignment", "Week 8", "40%", "LO2, LO3")

    outline.set_week(1, "Introduction to the unit; setting up the dev environment.")

    outline.save(os.path.join(script_dir, "Unit_Outline_generated.docx"))