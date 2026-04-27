"""First-run setup wizard for creating and initializing a KIW project."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.classification_config import (
    DEFAULT_CONFIG_FILENAME,
    ForceRule,
    load_classification_config,
    save_classification_config,
)
from services.project_service import PROJECT_DIR_NAME, ProjectContext


@dataclass(frozen=True, slots=True)
class PersonaOption:
    key: str
    icon: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class SetupWizardResult:
    context: ProjectContext
    persona_key: str
    persona_name: str
    documents_folder: Path
    output_folder: Path
    project_name: str


def list_personas() -> tuple[PersonaOption, ...]:
    """Return starter personas displayed in the setup wizard."""
    return (
        PersonaOption(
            key="marketing_professional",
            icon="🎯",
            name="Marketing Professional",
            description="Campaign strategy, ABM, pipeline and growth content.",
        ),
        PersonaOption(
            key="sales_professional",
            icon="💼",
            name="Sales Professional",
            description="Accounts, enablement, deal docs and customer interactions.",
        ),
        PersonaOption(
            key="consultant_freelancer",
            icon="🔧",
            name="Consultant / Freelancer",
            description="Client proposals, deliverables, statements of work.",
        ),
        PersonaOption(
            key="researcher_academic",
            icon="🔬",
            name="Researcher / Academic",
            description="Papers, literature notes, references and findings.",
        ),
        PersonaOption(
            key="developer_engineer",
            icon="💻",
            name="Developer / Engineer",
            description="Specs, architecture, implementation and code notes.",
        ),
    )


_PERSONA_TERMS: dict[str, tuple[str, ...]] = {
    "marketing_professional": ("campaign brief", "abm", "pipeline report", "go-to-market"),
    "sales_professional": ("sales deck", "account plan", "deal review", "forecast"),
    "consultant_freelancer": ("statement of work", "client proposal", "engagement plan", "retainer"),
    "researcher_academic": ("literature review", "methodology", "research notes", "dataset"),
    "developer_engineer": ("architecture", "technical design", "implementation notes", "runbook"),
}


def ensure_project_service_persona_api(project_service: Any) -> None:
    """Attach a lightweight apply_persona API to ProjectService instances that do not define one."""
    if hasattr(project_service, "apply_persona"):
        return

    def _apply_persona(*, output_folder: Path, persona: str) -> None:
        _apply_persona_defaults(output_folder=output_folder, persona=persona)

    setattr(project_service, "apply_persona", _apply_persona)


def _apply_persona_defaults(*, output_folder: Path, persona: str) -> None:
    """Update starter classification rules with persona-specific project keywords."""
    config_path = output_folder / PROJECT_DIR_NAME / DEFAULT_CONFIG_FILENAME
    config = load_classification_config(config_path)
    terms = _PERSONA_TERMS.get(persona, tuple())
    if not terms:
        return

    project_map = dict(config.project_map)
    for term in terms:
        project_map.setdefault(term.lower(), "ai_project")

    force_rules = list(config.force_rules)
    existing = {rule.contains.lower() for rule in force_rules}
    for term in terms:
        key = term.lower()
        if key in existing:
            continue
        force_rules.append(
            ForceRule(
                contains=term,
                category="ai_project",
                workspace="ai_projects",
                subfolder="persona_starters",
                reason="Persona starter rule",
            )
        )

    updated = type(config)(
        workspaces=dict(config.workspaces),
        force_rules=tuple(force_rules),
        negative_rules=tuple(config.negative_rules),
        company_map=dict(config.company_map),
        project_map=project_map,
        doc_type_patterns=tuple(config.doc_type_patterns),
        code_ext=dict(config.code_ext),
        rule_confidence=dict(config.rule_confidence),
        risky_keywords=tuple(config.risky_keywords),
        broad_keywords=tuple(config.broad_keywords),
        broad_match_force_review=config.broad_match_force_review,
        enable_ollama=config.enable_ollama,
        ollama_model=config.ollama_model,
        ai_provider=config.ai_provider,
        api_key=config.api_key,
        cloud_model=config.cloud_model,
        ai_mode=config.ai_mode,
        auto_assign_workspace=config.auto_assign_workspace,
        duplicate_filename_policy=config.duplicate_filename_policy,
        chunk_target_size=config.chunk_target_size,
        minimum_chunk_size=config.minimum_chunk_size,
        review_confidence_threshold=config.review_confidence_threshold,
        relevance_min_score=config.relevance_min_score,
        small_file_char_threshold=config.small_file_char_threshold,
        preflight_wiki_share_cap=config.preflight_wiki_share_cap,
    )
    save_classification_config(config_path, updated)


class PersonaCard(QToolButton):
    """Selectable card button used on the persona step."""

    selected = Signal()

    def __init__(self, persona: PersonaOption) -> None:
        super().__init__()
        self._persona = persona
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(180, 100)
        self.setMaximumSize(180, 100)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setText(f"{persona.icon}  {persona.name}\n{persona.description}")
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.setStyleSheet(
            """
            QToolButton {
                border: 1px solid #cfd4dc;
                border-radius: 12px;
                padding: 10px;
                text-align: left;
                background: #ffffff;
                font-size: 14px;
                line-height: 1.3;
            }
            QToolButton:hover {
                border-color: #6f7f95;
                background: #f6f9fc;
            }
            QToolButton:checked {
                border: 2px solid #1f6feb;
                background: #eef5ff;
            }
            """
        )
        self.toggled.connect(self._on_toggled)

    @property
    def persona(self) -> PersonaOption:
        return self._persona

    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self.selected.emit()


class SetupWizardDialog(QDialog):
    """Guided first-run project setup flow."""

    _category_generation_done = Signal(str)
    _category_generation_error = Signal(str)

    def __init__(self, *, project_service: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project Wizard")
        self.setModal(True)
        self.resize(860, 700)

        self._project_service = project_service
        ensure_project_service_persona_api(self._project_service)

        self._personas = list_personas()
        self._selected_persona = self._personas[0]
        self._step = 0
        self._result: SetupWizardResult | None = None
        self._last_suggested_name = ""
        self._pending_categories: str = ""
        self._applied_categories: dict = {}

        self._build_ui()
        self._category_generation_done.connect(self._on_generation_complete)
        self._category_generation_error.connect(self._on_generation_error)
        self._sync_step()

    @property
    def result_data(self) -> SetupWizardResult | None:
        return self._result

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        self._step_label = QLabel("Step 1 of 5")
        self._step_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(self._step_label)

        self._progress = QProgressBar()
        self._progress.setRange(1, 5)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #d7dce4;
                border-radius: 3px;
                background: #f3f5f8;
            }
            QProgressBar::chunk {
                border-radius: 2px;
                background: #1f6feb;
            }
            """
        )
        root.addWidget(self._progress)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step_welcome())
        self._stack.addWidget(self._build_step_persona())
        self._stack.addWidget(self._build_step_folders())
        self._stack.addWidget(self._build_step_categories())
        self._stack.addWidget(self._build_step_summary_ai())
        root.addWidget(self._stack, stretch=1)

        nav = QHBoxLayout()
        nav.setSpacing(10)
        self._cancel_btn = QPushButton("Cancel")
        self._back_btn = QPushButton("Back")
        self._next_btn = QPushButton("Next")
        self._finish_btn = QPushButton("Create My Project →")
        self._finish_btn.setDefault(True)

        nav.addWidget(self._cancel_btn)
        nav.addStretch(1)
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)
        nav.addWidget(self._finish_btn)
        root.addLayout(nav)

        self._cancel_btn.clicked.connect(self.reject)
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._finish_btn.clicked.connect(self._finish)

        self.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
            }
            QLineEdit {
                font-size: 16px;
                min-height: 34px;
            }
            QPushButton {
                font-size: 15px;
                min-height: 34px;
                padding: 4px 12px;
            }
            QRadioButton {
                font-size: 15px;
                min-height: 28px;
            }
            """
        )

    def _build_step_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("Welcome to Knowledge Intake Workbench")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        subtitle = QLabel("Organize your professional documents for AI tools like AnythingLLM and Open WebUI")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 16px; color: #516173;")

        body = QLabel(
            "This wizard will help you set up your first project in about 2 minutes. You'll need:\n\n"
            "• A folder containing your documents\n"
            "  (PDFs, Word docs, PowerPoints, markdown files)\n\n"
            "• A folder where you want the organized output saved\n\n"
            "That's it. Let's get started."
        )
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 16px;")

        self._get_started_btn = QPushButton("Get Started →")
        self._get_started_btn.setFixedWidth(180)
        self._get_started_btn.clicked.connect(lambda: self._set_step(1))

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addWidget(self._get_started_btn, alignment=Qt.AlignLeft)
        return page

    def _build_step_persona(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("What kind of professional are you?")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        subtitle = QLabel(
            "This sets up starter classification rules tailored to your work. "
            "You can customize them anytime."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 16px; color: #516173;")

        grid_host = QFrame()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        self._persona_group = QButtonGroup(self)
        self._persona_cards: list[PersonaCard] = []
        for idx, persona in enumerate(self._personas):
            card = PersonaCard(persona)
            row = idx // 2
            col = idx % 2
            grid.addWidget(card, row, col)
            self._persona_group.addButton(card, idx)
            card.selected.connect(lambda p=persona: self._on_persona_selected(p))
            self._persona_cards.append(card)

        self._persona_cards[0].setChecked(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(grid_host, alignment=Qt.AlignTop)
        layout.addStretch(1)
        return page

    def _build_step_folders(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        title = QLabel("Where are your documents?")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")

        docs_help = QLabel(
            "Documents folder\n"
            "The folder containing your PDFs, Word docs, PowerPoints, and notes"
        )
        docs_help.setWordWrap(True)
        docs_help.setStyleSheet("font-size: 16px;")

        docs_row = QHBoxLayout()
        self._docs_btn = QPushButton("Browse...")
        self._docs_btn.clicked.connect(self._browse_documents_folder)
        docs_row.addWidget(self._docs_btn)
        docs_row.addStretch(1)
        self._docs_path_label = QLabel("No folder selected")
        self._docs_path_label.setWordWrap(True)
        self._docs_path_label.setStyleSheet("font-size: 14px; color: #5b6776;")

        out_help = QLabel(
            "Output folder\n"
            "Where the organized files will be saved.\n"
            "Pick an empty folder or create a new one."
        )
        out_help.setWordWrap(True)
        out_help.setStyleSheet("font-size: 16px;")

        out_row = QHBoxLayout()
        self._out_btn = QPushButton("Browse...")
        self._out_btn.clicked.connect(self._browse_output_folder)
        out_row.addWidget(self._out_btn)
        out_row.addStretch(1)
        self._out_path_label = QLabel("No folder selected")
        self._out_path_label.setWordWrap(True)
        self._out_path_label.setStyleSheet("font-size: 14px; color: #5b6776;")

        name_lbl = QLabel("Project name")
        name_lbl.setStyleSheet("font-size: 16px;")
        self._project_name_edit = QLineEdit()
        self._project_name_edit.setPlaceholderText("My Knowledge Base")

        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(docs_help)
        layout.addLayout(docs_row)
        layout.addWidget(self._docs_path_label)
        layout.addSpacing(8)
        layout.addWidget(out_help)
        layout.addLayout(out_row)
        layout.addWidget(self._out_path_label)
        layout.addSpacing(8)
        layout.addWidget(name_lbl)
        layout.addWidget(self._project_name_edit)
        layout.addStretch(1)
        return page

    def _build_step_categories(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("What do you want to organize?")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Describe your professional background and KIWI will suggest categories "
            "automatically — or build them manually below."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 12px; color: #516173;")
        layout.addWidget(subtitle)

        # ── AI generation group ──────────────────────────────────────────
        ai_group = QGroupBox("Generate with AI")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setContentsMargins(12, 12, 12, 12)
        ai_layout.setSpacing(6)

        ai_desc = QLabel(
            "Describe yourself professionally in a few sentences. "
            "Include your roles, industries, companies you've worked for, and types of work you do."
        )
        ai_desc.setWordWrap(True)
        ai_desc.setStyleSheet("font-size: 11px; color: #516173;")
        ai_layout.addWidget(ai_desc)

        self.bio_input = QTextEdit()
        self.bio_input.setPlaceholderText(
            "Example: I'm a program manager with 12 years at Boeing and "
            "Lockheed Martin. I ran digital transformation projects, managed "
            "vendor relationships, created executive briefings, and led "
            "cross-functional teams on defense and commercial programs."
        )
        self.bio_input.setMinimumHeight(100)
        ai_layout.addWidget(self.bio_input)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("AI Provider:"))
        self.wizard_provider_combo = QComboBox()
        self.wizard_provider_combo.addItems(["ollama", "claude", "openai"])
        provider_row.addWidget(self.wizard_provider_combo)
        self.wizard_api_key_edit = QLineEdit()
        self.wizard_api_key_edit.setPlaceholderText("API key (if using Claude or OpenAI)")
        self.wizard_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        provider_row.addWidget(self.wizard_api_key_edit, 1)
        ai_layout.addLayout(provider_row)

        self.generate_btn = QPushButton("✨ Generate My Categories")
        self.generate_btn.setProperty("class", "btn-primary")
        self.generate_btn.clicked.connect(self.generate_categories)
        ai_layout.addWidget(self.generate_btn)

        self.generation_status = QLabel("")
        self.generation_status.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        ai_layout.addWidget(self.generation_status)

        layout.addWidget(ai_group)

        # ── Manual section ───────────────────────────────────────────────
        manual_group = QGroupBox("Build Manually")
        manual_layout = QHBoxLayout(manual_group)
        manual_layout.setContentsMargins(12, 12, 12, 12)
        manual_layout.setSpacing(12)

        ws_col = QVBoxLayout()
        ws_col.addWidget(QLabel("My Workspaces (top-level folders)"))
        ws_help = QLabel("These are your main topic buckets. Start with 3-6.")
        ws_help.setStyleSheet("font-size: 11px; color: #516173;")
        ws_help.setWordWrap(True)
        ws_col.addWidget(ws_help)
        self.wizard_workspace_list = QListWidget()
        self.wizard_workspace_list.setFixedHeight(120)
        ws_col.addWidget(self.wizard_workspace_list)
        ws_btn_row = QHBoxLayout()
        self.wizard_ws_edit = QLineEdit()
        self.wizard_ws_edit.setPlaceholderText("e.g. project_management")
        self.wizard_add_ws_btn = QPushButton("Add")
        self.wizard_remove_ws_btn = QPushButton("Remove")
        self.wizard_add_ws_btn.clicked.connect(self._add_wizard_workspace)
        self.wizard_remove_ws_btn.clicked.connect(self._remove_wizard_workspace)
        ws_btn_row.addWidget(self.wizard_ws_edit, 1)
        ws_btn_row.addWidget(self.wizard_add_ws_btn)
        ws_btn_row.addWidget(self.wizard_remove_ws_btn)
        ws_col.addLayout(ws_btn_row)
        manual_layout.addLayout(ws_col)

        co_col = QVBoxLayout()
        co_col.addWidget(QLabel("My Companies & Employers"))
        co_help = QLabel("Files mentioning these will be grouped in your archive workspace.")
        co_help.setStyleSheet("font-size: 11px; color: #516173;")
        co_help.setWordWrap(True)
        co_col.addWidget(co_help)
        self.wizard_company_list = QListWidget()
        self.wizard_company_list.setFixedHeight(120)
        co_col.addWidget(self.wizard_company_list)
        co_btn_row = QHBoxLayout()
        self.wizard_company_edit = QLineEdit()
        self.wizard_company_edit.setPlaceholderText("e.g. boeing, lockheed")
        self.wizard_add_company_btn = QPushButton("Add")
        self.wizard_remove_company_btn = QPushButton("Remove")
        self.wizard_add_company_btn.clicked.connect(self._add_wizard_company)
        self.wizard_remove_company_btn.clicked.connect(self._remove_wizard_company)
        co_btn_row.addWidget(self.wizard_company_edit, 1)
        co_btn_row.addWidget(self.wizard_add_company_btn)
        co_btn_row.addWidget(self.wizard_remove_company_btn)
        co_col.addLayout(co_btn_row)
        manual_layout.addLayout(co_col)

        layout.addWidget(manual_group)

        # ── Preview section ──────────────────────────────────────────────
        self.category_preview = QTextEdit()
        self.category_preview.setReadOnly(True)
        self.category_preview.setPlaceholderText(
            "Your generated categories will appear here for review before being applied..."
        )
        self.category_preview.setMinimumHeight(120)
        self.category_preview.setStyleSheet(
            "background: #1a1a2e; color: #90caf9; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self.category_preview)

        self.apply_categories_btn = QPushButton("Apply These Categories")
        self.apply_categories_btn.setProperty("class", "btn-primary")
        self.apply_categories_btn.setEnabled(False)
        self.apply_categories_btn.clicked.connect(self.apply_categories)
        layout.addWidget(self.apply_categories_btn)

        return page

    # ------------------------------------------------------------------ #
    # Category generation                                                  #
    # ------------------------------------------------------------------ #

    def generate_categories(self) -> None:
        bio = self.bio_input.toPlainText().strip()
        if not bio:
            self.generation_status.setText("Please describe yourself first.")
            return

        self.generate_btn.setEnabled(False)
        self.generation_status.setText("Generating categories...")

        provider = self.wizard_provider_combo.currentText()
        api_key = self.wizard_api_key_edit.text().strip()

        prompt = (
            "You are helping a professional organize their work documents.\n"
            "Based on this professional background description, generate a set of "
            "classification categories for organizing their files.\n\n"
            f"Background: {bio}\n\n"
            "Respond with ONLY a valid JSON object in exactly this format:\n"
            "{\n"
            '  "workspaces": {\n'
            '    "label1": "folder_name_1",\n'
            '    "label2": "folder_name_2"\n'
            "  },\n"
            '  "company_map": {\n'
            '    "company_keyword": "target_workspace_folder_name"\n'
            "  },\n"
            '  "project_map": {\n'
            '    "project_keyword": "target_workspace_folder_name"\n'
            "  },\n"
            '  "force_rules": [\n'
            "    {\n"
            '      "contains": "keyword or phrase",\n'
            '      "workspace": "target_workspace_folder_name",\n'
            '      "subfolder": "optional_subfolder_or_None",\n'
            '      "reason": "why this rule makes sense"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Guidelines:\n"
            "- Create 4-8 workspaces that reflect their actual work topics\n"
            "- Always include a \"career_portfolio\" workspace for resumes/bios\n"
            "- Always include an \"archive\" workspace for general company docs\n"
            "- Company names should map to \"archive\" workspace\n"
            "- Project keywords should map to the most relevant workspace\n"
            "- Force rules should cover their most common document types\n"
            "- Use lowercase_with_underscores for all folder names\n"
            "- Be specific to their background, not generic\n"
            "- Return ONLY the JSON, no explanation, no markdown fences"
        )

        import threading

        def _call_ai() -> None:
            try:
                result_json: str | None = None

                if provider == "ollama":
                    import requests  # type: ignore[import-untyped]
                    response = requests.post(
                        "http://127.0.0.1:11434/api/generate",
                        json={"model": "llama3.2:3b", "prompt": prompt, "stream": False},
                        timeout=60,
                    )
                    result_json = response.json().get("response", "")

                elif provider == "claude":
                    import anthropic  # type: ignore[import-untyped]
                    client = anthropic.Anthropic(api_key=api_key)
                    message = client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=1500,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    result_json = message.content[0].text

                elif provider == "openai":
                    import openai  # type: ignore[import-untyped]
                    client = openai.OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        max_tokens=1500,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    result_json = response.choices[0].message.content

                if result_json is None:
                    raise ValueError(f"Unknown provider: {provider}")

                clean = result_json.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1]
                if clean.endswith("```"):
                    clean = clean.rsplit("\n", 1)[0]
                clean = clean.strip()

                parsed = json.loads(clean)
                self._category_generation_done.emit(json.dumps(parsed, indent=2))

            except Exception as exc:  # noqa: BLE001
                self._category_generation_error.emit(str(exc))

        threading.Thread(target=_call_ai, daemon=True).start()

    @Slot(str)
    def _on_generation_complete(self, result: str) -> None:
        self._pending_categories = result
        self.category_preview.setPlainText(result)
        self.apply_categories_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.generation_status.setText(
            "✓ Categories generated. Review above and click Apply."
        )
        self.generation_status.setStyleSheet("color: #3d9970; font-size: 11px;")

    @Slot(str)
    def _on_generation_error(self, error: str) -> None:
        self.generate_btn.setEnabled(True)
        self.generation_status.setText(f"Generation failed: {error}")
        self.generation_status.setStyleSheet("color: #cc4444; font-size: 11px;")

    def apply_categories(self) -> None:
        try:
            data = json.loads(self._pending_categories)
            self._applied_categories = data
            self.generation_status.setText(
                "✓ Categories will be applied when you complete setup."
            )
            self.apply_categories_btn.setEnabled(False)
        except Exception as exc:  # noqa: BLE001
            self.generation_status.setText(f"Could not apply: {exc}")

    def _add_wizard_workspace(self) -> None:
        text = self.wizard_ws_edit.text().strip().lower().replace(" ", "_")
        if text:
            self.wizard_workspace_list.addItem(text)
            self.wizard_ws_edit.clear()

    def _remove_wizard_workspace(self) -> None:
        item = self.wizard_workspace_list.currentItem()
        if item:
            self.wizard_workspace_list.takeItem(self.wizard_workspace_list.row(item))

    def _add_wizard_company(self) -> None:
        text = self.wizard_company_edit.text().strip().lower()
        if text:
            self.wizard_company_list.addItem(text)
            self.wizard_company_edit.clear()

    def _remove_wizard_company(self) -> None:
        item = self.wizard_company_list.currentItem()
        if item:
            self.wizard_company_list.takeItem(self.wizard_company_list.row(item))

    def _merge_categories_into_config(self, *, output_folder: Path) -> None:
        """Merge AI-generated and manually entered categories into the project config, adding to defaults."""
        config_path = output_folder / PROJECT_DIR_NAME / DEFAULT_CONFIG_FILENAME
        config = load_classification_config(config_path)

        workspaces = dict(config.workspaces)
        company_map = dict(config.company_map)
        project_map = dict(config.project_map)
        force_rules = list(config.force_rules)
        existing_contains = {r.contains.lower() for r in force_rules}

        if self._applied_categories:
            cat = self._applied_categories
            for label, folder in cat.get("workspaces", {}).items():
                workspaces.setdefault(str(label), str(folder))
            for keyword, ws in cat.get("company_map", {}).items():
                company_map.setdefault(str(keyword), str(ws))
            for keyword, ws in cat.get("project_map", {}).items():
                project_map.setdefault(str(keyword), str(ws))
            for rule in cat.get("force_rules", []):
                contains = str(rule.get("contains", "")).strip()
                if not contains or contains.lower() in existing_contains:
                    continue
                subfolder = str(rule.get("subfolder", "")).strip()
                if subfolder in ("None", ""):
                    subfolder = None  # type: ignore[assignment]
                force_rules.append(
                    ForceRule(
                        contains=contains,
                        category=str(rule.get("workspace", "archive")),
                        workspace=str(rule.get("workspace", "")).strip() or None,
                        subfolder=subfolder,
                        reason=str(rule.get("reason", "")).strip() or None,
                    )
                )
                existing_contains.add(contains.lower())

        for i in range(self.wizard_workspace_list.count()):
            item = self.wizard_workspace_list.item(i)
            if item:
                ws_name = item.text().strip()
                if ws_name:
                    workspaces.setdefault(ws_name, ws_name)

        for i in range(self.wizard_company_list.count()):
            item = self.wizard_company_list.item(i)
            if item:
                company = item.text().strip().lower()
                if company:
                    company_map.setdefault(company, "archive")

        if (
            workspaces == dict(config.workspaces)
            and company_map == dict(config.company_map)
            and project_map == dict(config.project_map)
            and len(force_rules) == len(config.force_rules)
        ):
            return

        updated = type(config)(
            workspaces=workspaces,
            force_rules=tuple(force_rules),
            negative_rules=tuple(config.negative_rules),
            company_map=company_map,
            project_map=project_map,
            doc_type_patterns=tuple(config.doc_type_patterns),
            code_ext=dict(config.code_ext),
            rule_confidence=dict(config.rule_confidence),
            risky_keywords=tuple(config.risky_keywords),
            broad_keywords=tuple(config.broad_keywords),
            broad_match_force_review=config.broad_match_force_review,
            enable_ollama=config.enable_ollama,
            ollama_model=config.ollama_model,
            ai_provider=config.ai_provider,
            api_key=config.api_key,
            cloud_model=config.cloud_model,
            ai_mode=config.ai_mode,
            auto_assign_workspace=config.auto_assign_workspace,
            duplicate_filename_policy=config.duplicate_filename_policy,
            chunk_target_size=config.chunk_target_size,
            minimum_chunk_size=config.minimum_chunk_size,
            review_confidence_threshold=config.review_confidence_threshold,
            relevance_min_score=config.relevance_min_score,
            small_file_char_threshold=config.small_file_char_threshold,
            preflight_wiki_share_cap=config.preflight_wiki_share_cap,
        )
        save_classification_config(config_path, updated)

    def _build_step_summary_ai(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        title = QLabel("You're almost ready")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")

        self._summary_box = QTextEdit()
        self._summary_box.setReadOnly(True)
        self._summary_box.setFixedHeight(170)
        self._summary_box.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid #d3dae4;
                border-radius: 10px;
                background: #fbfcfe;
                font-size: 15px;
                padding: 8px;
            }
            """
        )

        self._ai_toggle = QToolButton()
        self._ai_toggle.setText("Optional: Connect an AI assistant for smarter classification")
        self._ai_toggle.setCheckable(True)
        self._ai_toggle.setChecked(False)
        self._ai_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._ai_toggle.setArrowType(Qt.RightArrow)
        self._ai_toggle.clicked.connect(self._toggle_ai_section)

        self._ai_section = QGroupBox()
        self._ai_section.setVisible(False)
        ai_layout = QVBoxLayout(self._ai_section)
        ai_layout.setContentsMargins(12, 12, 12, 12)

        explainer = QLabel(
            "KIW can use AI to help classify documents it's unsure about. "
            "This is optional — the app works without it using built-in rules."
        )
        explainer.setWordWrap(True)
        explainer.setStyleSheet("font-size: 15px; color: #556273;")

        self._radio_skip = QRadioButton("Skip for now (recommended for first run)")
        self._radio_ollama = QRadioButton("Use Ollama (free, runs on your computer)")
        self._radio_claude = QRadioButton("Use Claude API (requires Anthropic account)")
        self._radio_openai = QRadioButton("Use OpenAI API (requires OpenAI account)")
        self._radio_skip.setChecked(True)

        self._ai_group = QButtonGroup(self)
        self._ai_group.addButton(self._radio_skip)
        self._ai_group.addButton(self._radio_ollama)
        self._ai_group.addButton(self._radio_claude)
        self._ai_group.addButton(self._radio_openai)

        self._ollama_url_edit = QLineEdit("http://127.0.0.1:11434")
        self._claude_key_edit = QLineEdit()
        self._claude_key_edit.setPlaceholderText("Anthropic API key")
        self._claude_key_edit.setEchoMode(QLineEdit.Password)
        self._openai_key_edit = QLineEdit()
        self._openai_key_edit.setPlaceholderText("OpenAI API key")
        self._openai_key_edit.setEchoMode(QLineEdit.Password)

        self._ollama_row = self._labeled_row("Ollama URL", self._ollama_url_edit)
        self._claude_row = self._labeled_row("Claude API key", self._claude_key_edit)
        self._openai_row = self._labeled_row("OpenAI API key", self._openai_key_edit)

        self._radio_skip.toggled.connect(self._sync_ai_rows)
        self._radio_ollama.toggled.connect(self._sync_ai_rows)
        self._radio_claude.toggled.connect(self._sync_ai_rows)
        self._radio_openai.toggled.connect(self._sync_ai_rows)

        ai_layout.addWidget(explainer)
        ai_layout.addSpacing(8)
        ai_layout.addWidget(self._radio_skip)
        ai_layout.addWidget(self._radio_ollama)
        ai_layout.addWidget(self._ollama_row)
        ai_layout.addWidget(self._radio_claude)
        ai_layout.addWidget(self._claude_row)
        ai_layout.addWidget(self._radio_openai)
        ai_layout.addWidget(self._openai_row)

        layout.addWidget(title)
        layout.addWidget(self._summary_box)
        layout.addWidget(self._ai_toggle)
        layout.addWidget(self._ai_section)
        layout.addStretch(1)

        self._sync_ai_rows()
        return page

    def _labeled_row(self, label: str, editor: QLineEdit) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(20, 0, 0, 0)
        row.addWidget(QLabel(label))
        row.addWidget(editor, stretch=1)
        return host

    def _toggle_ai_section(self) -> None:
        expanded = self._ai_toggle.isChecked()
        self._ai_toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._ai_section.setVisible(expanded)

    def _sync_ai_rows(self) -> None:
        self._ollama_row.setVisible(self._radio_ollama.isChecked())
        self._claude_row.setVisible(self._radio_claude.isChecked())
        self._openai_row.setVisible(self._radio_openai.isChecked())

    def _set_step(self, step: int) -> None:
        self._step = max(0, min(4, step))
        self._sync_step()

    def _go_back(self) -> None:
        self._set_step(self._step - 1)

    def _go_next(self) -> None:
        if self._step == 2 and not self._validate_step_three(show_messages=True):
            return
        self._set_step(self._step + 1)

    def _sync_step(self) -> None:
        self._stack.setCurrentIndex(self._step)
        self._step_label.setText(f"Step {self._step + 1} of 5")
        self._progress.setValue(self._step + 1)
        self._back_btn.setEnabled(self._step > 0)
        self._next_btn.setVisible(self._step < 4)
        self._finish_btn.setVisible(self._step == 4)
        self._next_btn.setEnabled(self._step != 0)

        if self._step == 2:
            self._suggest_project_name_if_needed(force=False)
        if self._step == 4:
            if not self._validate_step_three(show_messages=False):
                self._set_step(2)
                return
            self._refresh_summary()

    def _on_persona_selected(self, persona: PersonaOption) -> None:
        self._selected_persona = persona
        self._suggest_project_name_if_needed(force=True)

    def _suggest_project_name_if_needed(self, *, force: bool) -> None:
        suggestion = f"My {self._selected_persona.name} Knowledge Base"
        current = self._project_name_edit.text().strip()
        if force and (not current or current == self._last_suggested_name):
            self._project_name_edit.setText(suggestion)
        elif not current:
            self._project_name_edit.setText(suggestion)
        self._last_suggested_name = suggestion

    def _browse_documents_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Documents Folder")
        if path:
            self._docs_path_label.setText(path)

    def _browse_output_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self._out_path_label.setText(path)

    def _validate_step_three(self, *, show_messages: bool) -> bool:
        docs_raw = self._docs_path_label.text().strip()
        out_raw = self._out_path_label.text().strip()
        if not docs_raw or docs_raw == "No folder selected":
            if show_messages:
                QMessageBox.warning(self, "Missing Folder", "Please choose a Documents folder.")
            return False
        if not out_raw or out_raw == "No folder selected":
            if show_messages:
                QMessageBox.warning(self, "Missing Folder", "Please choose an Output folder.")
            return False

        docs = Path(docs_raw).expanduser().resolve()
        out = Path(out_raw).expanduser().resolve()

        if not docs.is_dir():
            if show_messages:
                QMessageBox.warning(self, "Invalid Folder", "Documents folder does not exist.")
            return False
        if not out.is_dir():
            if show_messages:
                QMessageBox.warning(self, "Invalid Folder", "Output folder does not exist.")
            return False

        if out == docs:
            if show_messages:
                QMessageBox.warning(
                    self,
                    "Folder Conflict",
                    "Output folder cannot be the same as the documents folder.",
                )
            return False
        try:
            out.relative_to(docs)
            if show_messages:
                QMessageBox.warning(
                    self,
                    "Folder Conflict",
                    "Output folder cannot be inside the documents folder.",
                )
            return False
        except ValueError:
            pass

        return True

    def _refresh_summary(self) -> None:
        docs = self._docs_path_label.text().strip()
        out = self._out_path_label.text().strip()
        project_name = self._project_name_edit.text().strip() or "Knowledge Intake Project"
        lines = [
            f"✓ Profession: {self._selected_persona.name}",
            f"✓ Documents: {docs}",
            f"✓ Output: {out}",
            f"✓ Project: {project_name}",
        ]
        self._summary_box.setPlainText("\n".join(lines))

    def _finish(self) -> None:
        if not self._validate_step_three(show_messages=True):
            self._set_step(2)
            return

        docs = Path(self._docs_path_label.text().strip()).expanduser().resolve()
        out = Path(self._out_path_label.text().strip()).expanduser().resolve()
        project_name = self._project_name_edit.text().strip() or "Knowledge Intake Project"

        try:
            context = self._project_service.create_project(
                raw_folder=docs,
                output_folder=out,
                name=project_name,
            )
            self._project_service.apply_persona(
                output_folder=context.output_folder,
                persona=self._selected_persona.key,
            )
            self._merge_categories_into_config(output_folder=context.output_folder)
            self._save_ai_prefs_if_selected(output_folder=context.output_folder)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Setup Error", str(exc))
            return

        self._result = SetupWizardResult(
            context=context,
            persona_key=self._selected_persona.key,
            persona_name=self._selected_persona.name,
            documents_folder=docs,
            output_folder=out,
            project_name=project_name,
        )
        self.accept()

    def _save_ai_prefs_if_selected(self, *, output_folder: Path) -> None:
        payload: dict[str, str] = {}
        if self._radio_ollama.isChecked():
            payload = {
                "provider": "ollama",
                "base_url": self._ollama_url_edit.text().strip() or "http://127.0.0.1:11434",
            }
        elif self._radio_claude.isChecked():
            key = self._claude_key_edit.text().strip()
            if not key:
                raise ValueError("Claude API key is required when Claude is selected.")
            payload = {
                "provider": "claude",
                "api_key": key,
            }
        elif self._radio_openai.isChecked():
            key = self._openai_key_edit.text().strip()
            if not key:
                raise ValueError("OpenAI API key is required when OpenAI is selected.")
            payload = {
                "provider": "openai",
                "api_key": key,
            }

        if not payload:
            return
        target = output_folder / "ai_prefs.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
