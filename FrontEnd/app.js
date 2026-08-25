/* ============================================================
   MOCK BACKEND DATA
   Replace these localStorage operations with fetch() calls
   when your real backend/API is connected.
   ============================================================ */

const API_BASE_URL = ""; // e.g. "http://localhost:3000/api"

const defaultCourses = [
  {
    id: "spi-cs101",
    code: "CS101",
    name: "Software Engineering Fundamentals",
    semester: "Semester 2, 2026",
    startDate: "2026-07-20",
    description: "Foundations of software engineering, development practices and collaborative workflows.",
    outline: true
  },
  {
    id: "spi-it201",
    code: "IT201",
    name: "Database Systems",
    semester: "Semester 2, 2026",
    startDate: "2026-07-20",
    description: "Database fundamentals, data structures, SQL and server-side concepts.",
    outline: true
  },
  {
    id: "spi-ai301",
    code: "AI301",
    name: "Artificial Intelligence",
    semester: "Semester 2, 2026",
    startDate: "2026-08-03",
    description: "Introduction to AI tools, models, data-driven systems and practical applications.",
    outline: true
  }
];

/* Demo staff accounts. Replace with a real POST /api/auth/login call. */
const demoUsers = [
  { id: "admin-001", name: "Alex Admin", email: "admin@spi.edu.au", password: "password", role: "admin" },
  { id: "coursecoord-001", name: "Casey Coordinator", email: "coursecoord@spi.edu.au", password: "password", role: "course_coord" },
  { id: "unitcoord-001", name: "Uma Unit Coordinator", email: "unitcoord@spi.edu.au", password: "password", role: "unit_coord" }
];

const roleLabels = {
    admin: "Administrator",
    course_coord: "Course Coordinator",
    unit_coord: "Unit Coordinator"
};

function getStoredUsers() {
    return JSON.parse(localStorage.getItem("spi_users") || "[]");
}

function getCurrentUser() {
    return JSON.parse(localStorage.getItem("spi_current_user") || "null");
}

function getCoursesStore() {
    const existing = localStorage.getItem("spi_courses");
    if (!existing) {
        localStorage.setItem("spi_courses", JSON.stringify(defaultCourses));
        return [...defaultCourses];
    }
    return JSON.parse(existing);
}

function setCoursesStore(courses) {
    localStorage.setItem("spi_courses", JSON.stringify(courses));
}

/* ============================================================
   AUTHENTICATION
   ============================================================ */

function loginUser(email, password) {
    email = (email || document.getElementById("loginEmail").value.trim()).toLowerCase();
    password = password || document.getElementById("loginPassword").value;

    const error = document.getElementById("loginError");

    // Demo authentication. Replace with POST /api/auth/login.
    const match = demoUsers.find(u => u.email === email && u.password === password);

    if (match) {
        const user = { id: match.id, name: match.name, email: match.email, role: match.role };
        localStorage.setItem("spi_current_user", JSON.stringify(user));
        error.style.display = "none";
        showScreen("dashboardScreen");
        loadDashboard();
        showToast(`Welcome, ${match.name} (${roleLabels[match.role]})`);
        return true;
    }

    error.textContent = "Invalid login. Use one of the demo accounts listed below (password: password).";
    error.style.display = "block";
    return false;
}

function logoutUser() {
    localStorage.removeItem("spi_current_user");
    localStorage.removeItem("spi_active_course");
    showScreen("loginScreen");
    document.getElementById("loginForm").reset();
    showToast("You have been logged out");
}

function checkAuthSession() {
    const user = getCurrentUser();
    if (user) {
        showScreen("dashboardScreen");
        loadDashboard();
    } else {
        showScreen("loginScreen");
    }
}

/* ============================================================
   DASHBOARD / COURSES
   ============================================================ */

function loadDashboard() {
    const user = getCurrentUser();
    if (!user) return;

    document.getElementById("userPill").textContent = user.name;
    const rolePill = document.getElementById("userRolePill");
    rolePill.textContent = roleLabels[user.role] || user.role;

    // Only Administrators manage the master course list. Course/Unit
    // Coordinators can open and edit outlines but not add/delete/import/export courses.
    const isAdmin = user.role === "admin";
    document.getElementById("addCourseBtn").style.display = isAdmin ? "" : "none";
    document.getElementById("importLabel").style.display = isAdmin ? "" : "none";
    document.getElementById("dashboardSubtitle").textContent = isAdmin
        ? "Full course list — add, edit, or remove unit outlines."
        : "Unit outlines you can open and edit for your assigned courses.";

    const courses = fetchUserCourses(user.id);
    renderCourses(courses);
}

function fetchUserCourses(userId) {
    // Replace with:
    // return fetch(`${API_BASE_URL}/users/${userId}/courses`).then(...)
    return getCoursesStore();
}

function renderCourses(courses) {
    const grid = document.getElementById("courseGrid");

    if (!courses.length) {
        grid.innerHTML = `
          <div class="empty-state">
            <h3>No courses yet</h3>
            <p>Add a course to begin managing its unit outline.</p>
          </div>`;
        return;
    }

    const user = getCurrentUser();
    const isAdmin = user && user.role === "admin";

    grid.innerHTML = courses.map(course => `
      <article class="course-card">
        <div class="course-code">${escapeHtml(course.code)}</div>
        <h3>${escapeHtml(course.name)}</h3>
        <p>${escapeHtml(course.description || "Unit outline available for this course.")}</p>
        <div class="course-meta">
          <span>${escapeHtml(course.semester || "Current semester")}</span>
          <span>📅 Starts ${formatStartDate(course.startDate)}</span>
          <span>Unit Outline</span>
        </div>
        <div class="course-buttons">
          <button class="btn btn-primary" onclick="openCourse('${course.id}')">Open Outline</button>
          ${isAdmin ? `<button class="btn btn-outline" onclick="openEditCourseModal('${course.id}')">Edit</button>` : ""}
          ${isAdmin ? `<button class="btn btn-warning" onclick="deleteCourse('${course.id}')">Delete</button>` : ""}
        </div>
      </article>
    `).join("");
}

let courseModalEditingId = null; // null = "Add" mode, otherwise the course id being edited

function openAddCourseModal() {
    courseModalEditingId = null;
    document.getElementById("courseModalTitle").textContent = "Add Course";
    document.getElementById("courseModalSubmitBtn").textContent = "Add Course";
    document.getElementById("newCode").value = "";
    document.getElementById("newName").value = "";
    document.getElementById("newSemester").value = "";
    document.getElementById("newStartDate").value = "";
    document.getElementById("newDescription").value = "";
    document.getElementById("courseModal").classList.add("open");
}

function openEditCourseModal(courseId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;

    courseModalEditingId = courseId;
    document.getElementById("courseModalTitle").textContent = "Edit Course";
    document.getElementById("courseModalSubmitBtn").textContent = "Save Changes";
    document.getElementById("newCode").value = course.code || "";
    document.getElementById("newName").value = course.name || "";
    document.getElementById("newSemester").value = course.semester || "";
    document.getElementById("newStartDate").value = course.startDate || "";
    document.getElementById("newDescription").value = course.description || "";
    document.getElementById("courseModal").classList.add("open");
}

function closeAddCourseModal() {
    document.getElementById("courseModal").classList.remove("open");
    courseModalEditingId = null;
}

function submitAddCourse() {
    const code = document.getElementById("newCode").value.trim();
    const name = document.getElementById("newName").value.trim();
    const semester = document.getElementById("newSemester").value.trim();
    const startDate = document.getElementById("newStartDate").value;
    const description = document.getElementById("newDescription").value.trim();

    if (!code || !name) {
        showToast("Course code and course name are required");
        return;
    }

    if (courseModalEditingId) {
        updateCourse(courseModalEditingId, { code, name, semester, startDate, description });
        showToast("Course updated");
    } else {
        addCourse({ code, name, semester, startDate, description });
    }

    closeAddCourseModal();
}

function updateCourse(courseId, updates) {
    const courses = getCoursesStore();
    const idx = courses.findIndex(c => c.id === courseId);
    if (idx === -1) return null;

    courses[idx] = { ...courses[idx], ...updates };
    setCoursesStore(courses);
    loadDashboard();
    return courses[idx];
}

/* ============================================================
   REQUEST A CHANGE
   For fields outside a Unit/Course Coordinator's editable domain,
   this logs a request (locally, for this demo) instead of an
   uncontrolled direct edit.
   ============================================================ */

function getChangeRequestsStore() {
    return JSON.parse(localStorage.getItem("spi_change_requests") || "[]");
}

function saveChangeRequestsStore(requests) {
    localStorage.setItem("spi_change_requests", JSON.stringify(requests));
}

function openChangeRequestModal() {
    const user = getCurrentUser();
    const role = user ? user.role : "unit_coord";

    if (role === "admin") {
        // Admins edit everything directly — nothing to request.
        return;
    }

    const options = restrictedSections[role] || [];
    const select = document.getElementById("crSection");
    select.innerHTML = options.map(opt => `<option>${escapeHtml(opt)}</option>`).join("")
        + `<option>Other</option>`;

    document.getElementById("changeRequestModal").classList.add("open");
}

function closeChangeRequestModal() {
    document.getElementById("changeRequestModal").classList.remove("open");
}

function submitChangeRequest() {
    const section = document.getElementById("crSection").value;
    const details = document.getElementById("crDetails").value.trim();
    const reason = document.getElementById("crReason").value.trim();

    if (!details) {
        showToast("Please describe the change you're requesting");
        return;
    }

    const user = getCurrentUser();
    const course = JSON.parse(localStorage.getItem("spi_active_course") || "null");

    const requests = getChangeRequestsStore();
    requests.push({
        id: "cr-" + Date.now(),
        courseId: course ? course.id : null,
        courseCode: course ? course.code : "—",
        courseName: course ? course.name : "—",
        requestedBy: user ? user.name : "Unknown",
        requestedByRole: user ? (roleLabels[user.role] || user.role) : "—",
        section,
        details,
        reason,
        status: "pending",
        createdAt: new Date().toISOString()
    });
    saveChangeRequestsStore(requests);

    document.getElementById("crDetails").value = "";
    document.getElementById("crReason").value = "";
    closeChangeRequestModal();
    showToast("Change request submitted for review");
}

function addCourse(courseData) {
    const courses = getCoursesStore();
    const course = {
        id: "course-" + Date.now(),
        ...courseData,
        outline: true
    };
    courses.push(course);
    setCoursesStore(courses);
    loadDashboard();
    showToast("Course added successfully");
    return course;
}

function deleteCourse(courseId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;

    if (!confirm(`Delete ${course.code} — ${course.name}?`)) return;

    const courses = getCoursesStore().filter(c => c.id !== courseId);
    setCoursesStore(courses);
    loadDashboard();
    showToast("Course deleted");
}

function openCourse(courseId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;

    localStorage.setItem("spi_active_course", JSON.stringify(course));
    showScreen("unitScreen");

    // Update the existing unit-outline UI with the selected course.
    document.getElementById("unit_code").value = course.code;
    document.getElementById("title").value = course.name;
    document.getElementById("disp_organisation").textContent = "Sydney Polytechnic Institute";

    const user = getCurrentUser();
    if (user) {
        document.getElementById("unitUserPill").textContent = `${user.name} — ${roleLabels[user.role] || user.role}`;
    }

    calculateTotalHours();
    checkAssessmentTotal();
    updateRolePermissions();
    initAutoGrowTextareas();
    showToast(`Opened ${course.code}`);
}

/* Auto-expanding textareas: grows the box to fit content as the user
   types or presses Enter, instead of scrolling text inside a fixed box. */
function autoGrowTextarea(el) {
    el.style.height = "auto";
    el.style.height = (el.scrollHeight) + "px";
}

function initAutoGrowTextareas() {
    document.querySelectorAll("textarea.auto-grow").forEach(el => {
        autoGrowTextarea(el);
    });
}

function fetchCourseData(courseId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    return course || null;
}

/* ============================================================
   UNIT OUTLINE SAVE / BACKEND DATA
   ============================================================ */

function collectOutlineData() {
    const fields = document.querySelectorAll("#unitScreen [id]");
    const data = {};

    fields.forEach(el => {
        if (!el.id) return;
        if (el.matches("input, textarea, select")) data[el.id] = el.value;
    });

    return data;
}

function saveCourseChanges(courseId, outlineData) {
    const courses = getCoursesStore();
    const index = courses.findIndex(c => c.id === courseId);
    if (index === -1) return false;

    courses[index].outlineData = outlineData;
    setCoursesStore(courses);

    // Replace localStorage persistence with:
    // fetch(`${API_BASE_URL}/courses/${courseId}`, {
    //   method: "PUT",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify(outlineData)
    // });

    return true;
}

function saveChanges() {
    const orgName = document.getElementById("organisation").value;
    document.getElementById("disp_organisation").innerText = orgName;

    const active = JSON.parse(localStorage.getItem("spi_active_course") || "null");
    if (active) {
        saveCourseChanges(active.id, collectOutlineData());
    }

    showToast("Unit Outline changes saved");
}

function exportCourseData(courseId, format = "json") {
    const course = fetchCourseData(courseId);
    if (!course) return;

    if (format !== "json") {
        showToast("This demo currently exports JSON. PDF can be connected to a backend later.");
        return;
    }

    const blob = new Blob([JSON.stringify(course, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${course.code}-unit-outline.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function exportAllCourses() {
    const blob = new Blob([JSON.stringify(getCoursesStore(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "spi-courses.json";
    a.click();
    URL.revokeObjectURL(url);
    showToast("Courses exported");
}

function importCourseData(file) {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = event => {
        try {
            const imported = JSON.parse(event.target.result);
            const courses = Array.isArray(imported) ? imported : [imported];

            courses.forEach(course => {
                if (!course.id) course.id = "imported-" + Date.now() + "-" + Math.random().toString(16).slice(2);
            });

            const current = getCoursesStore();
            setCoursesStore([...current, ...courses]);
            loadDashboard();
            showToast(`${courses.length} course(s) imported`);
        } catch (err) {
            showToast("Import failed: invalid JSON file");
        }
    };
    reader.readAsText(file);
}

function validateCourseData(courseData) {
    return !!(courseData && courseData.code && courseData.name);
}

function showMessage(message, type = "info") {
    showToast(message, type);
}

/* ============================================================
   EXISTING UNIT OUTLINE FUNCTIONS
   These are retained from the supplied codebase.
   ============================================================ */

function calculateTotalHours() {
    const timetabled = parseFloat(document.getElementById("timetabled_hours").value) || 0;
    const personal = parseFloat(document.getElementById("personal_hours").value) || 0;
    const total = timetabled + personal;
    document.getElementById("total_hours_disp").innerText = total + " Hours";
}

function checkAssessmentTotal() {
    const w1 = parseFloat(document.getElementById("ass1_weight").value) || 0;
    const w2 = parseFloat(document.getElementById("ass2_weight").value) || 0;
    const w3 = parseFloat(document.getElementById("ass3_weight").value) || 0;
    const w4 = parseFloat(document.getElementById("ass4_weight").value) || 0;
    const w5 = parseFloat(document.getElementById("ass5_weight").value) || 0;

    const sum = w1 + w2 + w3 + w4 + w5;
    const box = document.getElementById("weightTotalBox");
    const text = document.getElementById("weightSumText");

    if (sum === 100) {
        box.className = "weight-total-box weight-pass";
        text.innerText = sum + "% (Valid - Sum equals 100%)";
    } else {
        box.className = "weight-total-box weight-fail";
        text.innerText = sum + "% (Invalid - Total must equal 100%)";
    }
}

/* Sections each non-admin role is restricted from — i.e. the fields
   they'd need to raise a change request for instead of editing directly.
   Kept in sync with the data-perm attributes used across the outline. */
const restrictedSections = {
    course_coord: [
        "Unit Details (code, name, credit points, award)",
        "Study Hours & Mode",
        "Requirements / Prerequisites",
        "Unit Description",
        "Resources & Governance (Policy links, AI tools statement)"
    ],
    unit_coord: [
        "Unit Details (code, name, credit points, award)",
        "Study Hours & Mode",
        "Requirements / Prerequisites",
        "Unit Description",
        "Learning Outcomes",
        "Assessment Weighting & LOs Assessed",
        "Resources & Governance (Policy links, AI tools statement)"
    ]
};

function updateRolePermissions() {
    const user = getCurrentUser();
    const role = user ? user.role : "unit_coord";
    const roleTitle = document.getElementById("currentRoleTitle");
    const roleDesc = document.getElementById("currentRoleDesc");
    const requestBtn = document.getElementById("requestChangeBtn");

    if (role === "admin") {
        roleTitle.innerText = "Administrator";
        roleDesc.innerText = "Full Read/Write access to all administrative, academic, assessment, and weekly activity fields.";
        // Admins can edit everything directly, so there's nothing to request.
        if (requestBtn) requestBtn.style.display = "none";
    } else if (role === "course_coord") {
        roleTitle.innerText = "Course Coordinator";
        roleDesc.innerText = "Read/Write access to Learning Outcomes, Assessment Weights, and Unit Coordinator editable fields. Use \"Request a Change\" for Administrator-only fields.";
        if (requestBtn) requestBtn.style.display = "";
    } else {
        roleTitle.innerText = "Unit Coordinator";
        roleDesc.innerText = "Read/Write access to Assessment Descriptions, Due Dates, Weekly Activities, Textbooks, and Student Feedback. Use \"Request a Change\" for anything else.";
        if (requestBtn) requestBtn.style.display = "";
    }

    document.querySelectorAll("#unitScreen [data-perm]").forEach(el => {
        const perm = el.getAttribute("data-perm");
        let canEdit = false;

        if (role === "admin") canEdit = true;
        else if (role === "course_coord") canEdit = perm === "course_coord" || perm === "unit_coord";
        else if (role === "unit_coord") canEdit = perm === "unit_coord";

        el.disabled = !canEdit;
    });
}

function print_pdf() {
    const active = JSON.parse(localStorage.getItem("spi_active_course") || "null");
    if (active) {
        exportCourseData(active.id, "json");
    } else {
        window.print();
    }
}

function returnToDashboard() {
    saveChanges();
    showScreen("dashboardScreen");
    loadDashboard();
}

function showScreen(id) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById(id).classList.add("active");
    window.scrollTo(0,0);
}

function showToast(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
    })[ch]);
}

function formatStartDate(dateStr) {
    if (!dateStr) return "TBA";
    // Parse as a plain calendar date (avoids UTC-shift off-by-one issues).
    const [y, m, d] = dateStr.split("-").map(Number);
    if (!y || !m || !d) return "TBA";
    const date = new Date(y, m - 1, d);
    return date.toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
}

window.addEventListener("load", () => {
    getCoursesStore();
    checkAuthSession();
    calculateTotalHours();
    checkAssessmentTotal();
    updateRolePermissions();
});
