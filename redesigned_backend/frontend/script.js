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

const roleLabels = {
    admin: "Administrator",
    course_coord: "Course Coordinator",
    unit_coord: "Unit Coordinator"
};

function getCurrentUser() {
    return JSON.parse(localStorage.getItem("spi_current_user") || "null");
}

/* ============================================================
   COURSES

   The LIST of courses (which ones exist, their code/name/semester/
   start date/description) is now real — synced from
   GET /dashboard/api/courses. Each course's actual outline CONTENT
   (outlineData, version history) is still stored locally in the
   browser only — that's waiting on the editing group's decision on
   how outline content gets structured/saved (see
   retrieve_database.py's save_doc()). syncCoursesFromBackend() below
   merges the two: server-side metadata + whatever's already cached
   locally for that course's content.
   ============================================================ */

function getCoursesStore() {
    const existing = localStorage.getItem("spi_courses");
    if (!existing) {
        // Fallback only for before the first successful backend sync
        // (e.g. offline, or the backend/DB isn't running yet during
        // development) — syncCoursesFromBackend() replaces this with
        // the real list as soon as it succeeds.
        localStorage.setItem("spi_courses", JSON.stringify(defaultCourses));
        return [...defaultCourses];
    }
    return JSON.parse(existing);
}

function setCoursesStore(courses) {
    localStorage.setItem("spi_courses", JSON.stringify(courses));
}

/* Pulls the real course list from the backend and merges it into the
   local store: server-side fields (code/name/semester/startDate/
   description) come from the database; outlineData/versionHistory for
   any course that already had some stay exactly as they were. New
   courses (created on the server, not seen locally yet) get default
   client-side fields, same as brand-new courses always have. Courses
   deleted server-side drop out of the local list too. */
async function syncCoursesFromBackend() {
    const response = await fetch("/dashboard/api/courses", { credentials: "same-origin" });
    if (!response.ok) {
        throw new Error(`Server responded ${response.status} ${response.statusText}`);
    }
    const backendCourses = await response.json();

    const local = getCoursesStore();
    const localByCode = new Map(local.map(c => [c.code, c]));

    const merged = backendCourses.map(bc => {
        const existing = localByCode.get(bc.code) || {};
        return {
            ...existing,
            id: String(bc.id),
            code: bc.code,
            name: bc.name,
            semester: bc.semester,
            startDate: bc.startDate,
            description: bc.description,
            outline: true,
        };
    });

    setCoursesStore(merged);
    return merged;
}

/* One-time fresh start: wipes any Version History accumulated by earlier
   builds of this app (each course keeps its current outline data — only
   the list of past versions is cleared) and any leftover admin review
   notes on change requests, then marks itself done so it never runs
   again on this browser. Bump the flag name if a future reset is ever
   needed again. */
const VERSION_HISTORY_RESET_FLAG = "spi_version_history_reset_v1";

function freshStartVersionHistory() {
    if (localStorage.getItem(VERSION_HISTORY_RESET_FLAG)) return;

    const courses = getCoursesStore();
    let changed = false;
    courses.forEach(c => {
        if (c.versionHistory) { delete c.versionHistory; changed = true; }
    });
    if (changed) setCoursesStore(courses);

    const requests = JSON.parse(localStorage.getItem("spi_change_requests") || "[]");
    let requestsChanged = false;
    requests.forEach(r => {
        if ("reviewNote" in r) { delete r.reviewNote; requestsChanged = true; }
    });
    if (requestsChanged) localStorage.setItem("spi_change_requests", JSON.stringify(requests));

    localStorage.setItem(VERSION_HISTORY_RESET_FLAG, "1");
}

function screenForRole(role) {
    // Staff management now happens entirely in Azure AD (accounts and
    // role assignment) — there's no in-app screen for it anymore, so
    // every role lands on the same dashboard.
    return "dashboardScreen";
}

/* Navigates to the correct home screen for whoever is logged in, and
   loads that screen's data. Used after login, on page load, and when
   returning from the Unit Outline screen. */
function goToHomeScreen() {
    const user = getCurrentUser();
    if (!user) {
        showScreen("loginScreen");
        return;
    }
    showScreen(screenForRole(user.role));
    loadDashboard();
}

/* ============================================================
   AUTHENTICATION

   Login itself now happens on the backend via Microsoft OAuth
   (auth_bp in server.py) — the "Sign in with Microsoft" link in
   index_1.html just goes straight to /login. This section's job is
   just: on page load, ask the backend whether there's a valid session
   (GET /api/session), and reflect that here.
   ============================================================ */

async function checkAuthSession() {
    try {
        const response = await fetch("/api/session", { credentials: "same-origin" });
        const data = await response.json();

        if (data.logged_in) {
            const user = { name: data.name, email: data.email, role: data.role };
            const isNewLogin = !getCurrentUser();
            localStorage.setItem("spi_current_user", JSON.stringify(user));

            goToHomeScreen();
            if (isNewLogin) showToast(`Welcome, ${user.name} (${roleLabels[user.role] || user.role})`);
            return;
        }
    } catch (err) {
        // Backend unreachable, or /api/session isn't there yet -- fall
        // through to the login screen rather than trusting whatever
        // was last cached in localStorage.
        console.error("Could not reach /api/session:", err);
    }

    localStorage.removeItem("spi_current_user");
    showScreen("loginScreen");
    showLoginErrorFromUrl();
    checkDevMode();
}

/* Shows the dev-login buttons (see /dev-login/<role> in server.py)
   only when the backend has DEV_MODE explicitly turned on -- this is
   purely a display check, the real gate is server-side, so hiding the
   panel here isn't what makes dev login safe, the env var is. */
async function checkDevMode() {
    try {
        const response = await fetch("/api/dev-mode", { credentials: "same-origin" });
        const data = await response.json();
        document.getElementById("devLoginPanel").style.display = data.enabled ? "block" : "none";
    } catch (err) {
        // Backend unreachable -- leave the dev panel hidden.
    }
}

/* auth_bp redirects failed logins back to /?login_error=... (see
   server.py) instead of showing a bare error page. This reads that
   and displays it on the login card, then cleans it out of the URL so
   refreshing the page doesn't keep re-showing it. */
function showLoginErrorFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const message = params.get("login_error");
    if (!message) return;

    const error = document.getElementById("loginError");
    error.textContent = message;
    error.style.display = "block";

    params.delete("login_error");
    const clean = window.location.pathname + (params.toString() ? `?${params}` : "");
    window.history.replaceState({}, "", clean);
}

function logoutUser() {
    localStorage.removeItem("spi_current_user");
    localStorage.removeItem("spi_active_course");
    localStorage.removeItem("spi_active_review_request");
    // /logout clears the server-side session and hands off to
    // Microsoft's own logout page (see server.py) -- a local
    // showScreen("loginScreen") alone would leave the Microsoft side
    // of the session still signed in.
    window.location.href = "/logout";
}

/* ============================================================
   DASHBOARD / COURSES
   ============================================================ */

async function loadDashboard() {
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

    // Change request visibility is tracked in this UI (submit + show
    // status), not acted on here — the actual review/approval happens in
    // the backend workflow system. Only Administrators see this.
    const changeRequestsBtn = document.getElementById("changeRequestsBtn");
    changeRequestsBtn.style.display = isAdmin ? "" : "none";
    if (isAdmin) {
        const pendingCount = getChangeRequestsStore().filter(r => r.status === "pending").length;
        document.getElementById("crNavBadge").textContent = pendingCount;
    }

    try {
        await syncCoursesFromBackend();
    } catch (err) {
        console.error("Could not load courses from the backend:", err);
        showToast("Could not reach the server — showing cached/demo courses");
    }

    const courses = fetchUserCourses(user.id);
    renderCourses(courses);

    // Pull the unit list from the Python backend (see bottom of file).
    loadUnitsFromBackend();
}

function fetchUserCourses(userId) {
    // The backend already returns the right set for this user (all
    // courses for admins, only their assigned courses for everyone
    // else — see /dashboard/api/courses in dashboard.py), and
    // syncCoursesFromBackend() (called just before this, in
    // loadDashboard()) has already put that into the local store. This
    // just reads it back out.
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
          <span>Starts ${formatStartDate(course.startDate)}</span>
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

async function submitAddCourse() {
    const code = document.getElementById("newCode").value.trim();
    const name = document.getElementById("newName").value.trim();
    const semester = document.getElementById("newSemester").value.trim();
    const startDate = document.getElementById("newStartDate").value;
    const description = document.getElementById("newDescription").value.trim();

    if (!code || !name) {
        showToast("Course code and course name are required");
        return;
    }

    try {
        if (courseModalEditingId) {
            await updateCourse(courseModalEditingId, { code, name, semester, startDate, description });
            showToast("Course updated");
        } else {
            await addCourse({ code, name, semester, startDate, description });
        }
        closeAddCourseModal();
    } catch (err) {
        console.error("Could not save course:", err);
        showToast("Could not save the course — check the server is running");
    }
}

/* All three of these hit the real backend (/dashboard/api/courses),
   then re-sync + re-render so the dashboard reflects what the server
   actually has (rather than assuming the write succeeded and editing
   the local copy directly). */

async function updateCourse(courseId, updates) {
    const response = await fetch(`/dashboard/api/courses/${courseId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(updates),
    });
    if (!response.ok) {
        throw new Error(`Server responded ${response.status} ${response.statusText}`);
    }
    const updated = await response.json();
    await syncCoursesFromBackend();
    loadDashboard();
    return updated;
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

// A change-request record bundles the individually queued field changes
// into one items[] array (see submitChangeRequest()). This normalizes
// any older record saved before bundling existed — back when a request
// stored a single section/details/reason — into the same one-item-list
// shape, so both render and resolve identically everywhere else.
function changeRequestItems(request) {
    if (Array.isArray(request.items) && request.items.length) return request.items;
    if (request.section || request.details) {
        return [{ section: request.section, details: request.details, reason: request.reason }];
    }
    return [];
}

// Rolls a bundled request's items into one line for the version-history
// note (e.g. "2 changes: Weekly Schedule: Swap Week 5 & 6; Assessment
// Schedule: Move due date"), so a single approved request that changed
// several fields still shows as ONE readable entry in Version History.
function summarizeChangeRequestItems(items) {
    if (!items || !items.length) return "a change request";
    const list = items.map(it => `${it.section}: ${it.details}`).join("; ");
    return items.length > 1 ? `${items.length} changes — ${list}` : list;
}

let changeRequestQueue = [];

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

    changeRequestQueue = [];
    document.getElementById("crDetails").value = "";
    document.getElementById("crReason").value = "";
    document.getElementById("crApproverEmail").value = "";
    renderChangeRequestQueue();

    document.getElementById("changeRequestModal").classList.add("open");
}

function closeChangeRequestModal() {
    document.getElementById("changeRequestModal").classList.remove("open");
    changeRequestQueue = [];
}

function renderChangeRequestQueue() {
    const list = document.getElementById("crQueueList");
    const empty = document.getElementById("crQueueEmpty");
    const submitBtn = document.getElementById("crSubmitBtn");

    if (!changeRequestQueue.length) {
        list.innerHTML = "";
        empty.style.display = "block";
        submitBtn.textContent = "Submit Request";
        return;
    }

    empty.style.display = "none";
    list.innerHTML = changeRequestQueue.map((item, index) => `
      <div class="cr-queue-item">
        <div class="cr-queue-item-body">
          <div class="cr-queue-item-section">${escapeHtml(item.section)}</div>
          <div class="cr-queue-item-details">${escapeHtml(item.details)}</div>
          ${item.reason ? `<div class="cr-queue-item-reason">Reason: ${escapeHtml(item.reason)}</div>` : ""}
        </div>
        <button type="button" class="cr-queue-remove" title="Remove" onclick="removeQueuedChangeRequest(${index})">×</button>
      </div>
    `).join("");

    submitBtn.textContent = `Submit ${changeRequestQueue.length} Request${changeRequestQueue.length > 1 ? "s" : ""}`;
}

function addChangeRequestToQueue() {
    const section = document.getElementById("crSection").value;
    const details = document.getElementById("crDetails").value.trim();
    const reason = document.getElementById("crReason").value.trim();

    if (!details) {
        showToast("Please describe the change before adding it to the list");
        return;
    }

    changeRequestQueue.push({ section, details, reason });

    document.getElementById("crDetails").value = "";
    document.getElementById("crReason").value = "";
    renderChangeRequestQueue();
    showToast("Added to your request list — add another or submit when ready");
}

function removeQueuedChangeRequest(index) {
    changeRequestQueue.splice(index, 1);
    renderChangeRequestQueue();
}

async function submitChangeRequest() {
    // If the person typed a change but forgot to click "Add to Request
    // List", fold it in automatically so a single quick request still
    // works in one click like before.
    const pendingDetails = document.getElementById("crDetails").value.trim();
    if (pendingDetails) {
        changeRequestQueue.push({
            section: document.getElementById("crSection").value,
            details: pendingDetails,
            reason: document.getElementById("crReason").value.trim()
        });
    }

    if (!changeRequestQueue.length) {
        showToast("Please describe at least one requested change");
        return;
    }

    const approverEmail = document.getElementById("crApproverEmail").value.trim();
    if (!approverEmail) {
        showToast("Please enter the approver's email");
        return;
    }

    const user = getCurrentUser();
    const course = JSON.parse(localStorage.getItem("spi_active_course") || "null");
    const items = changeRequestQueue.map(item => ({
        section: item.section, details: item.details, reason: item.reason
    }));

    // This is the real thing now, not a local simulation: it creates a
    // real approval record and sends a real email to approverEmail
    // (see /api/change-requests in app.py).
    let token;
    try {
        const response = await fetch("/api/change-requests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({
                unit_code: course ? course.code : "",
                coordinator_email: approverEmail,
                items,
            }),
        });
        if (!response.ok) {
            throw new Error(`Server responded ${response.status} ${response.statusText}`);
        }
        const created = await response.json();
        token = created.token;
    } catch (err) {
        console.error("Could not send the approval email:", err);
        showToast("Could not send the approval email — check the server is running");
        return;
    }

    const requests = getChangeRequestsStore();
    // Bundle every queued item into ONE change-request record (items[])
    // instead of a separate record per item. That way the request is
    // approved/rejected as a single email decision, applying every
    // queued change in one save — so the unit outline advances by
    // exactly one version (e.g. 2.0), rather than bumping once per
    // individual field change.
    requests.push({
        id: "cr-" + Date.now() + "-" + Math.random().toString(16).slice(2),
        courseId: course ? course.id : null,
        courseCode: course ? course.code : "—",
        courseName: course ? course.name : "—",
        requestedBy: user ? user.name : "Unknown",
        requestedByRole: user ? (roleLabels[user.role] || user.role) : "—",
        coordinatorEmail: approverEmail,
        // Links this local record to the real approval row — see
        // pollChangeRequestStatuses(), which is what actually moves
        // this out of "pending" once the approver responds by email.
        token,
        items,
        status: "pending",
        createdAt: new Date().toISOString()
    });
    saveChangeRequestsStore(requests);

    const count = changeRequestQueue.length;
    changeRequestQueue = [];
    document.getElementById("crDetails").value = "";
    document.getElementById("crReason").value = "";
    document.getElementById("crApproverEmail").value = "";
    renderChangeRequestQueue();
    closeChangeRequestModal();
    showToast(`Change request submitted — an approval email was sent to ${approverEmail}`);
}

/* ============================================================
   CHANGE REQUESTS — ADMIN VIEW
   The real approve/reject decision now happens via email — the
   approver clicks Approve/Reject in the email sent from
   submitChangeRequest() (see app.py's /api/change-requests), which
   hits /approve or /reject and updates the real approvals table.

   This screen doesn't decide anything itself: pollChangeRequestStatuses()
   below checks each pending request's real status (GET
   /api/change-requests/<token>) and updates it here once the approver
   has responded. For requests with a token, the old manual "Mark
   Approved / Mark Rejected" buttons are replaced with a "waiting on
   email" indicator — clicking those wouldn't touch the real approval
   record, so keeping them would just be misleading. They're kept ONLY
   as a fallback for any request created before this was wired up
   (no token) — resolveChangeRequest() below still exists for that case.

   The "Open Unit Outline" button lets an Administrator open the outline
   to reflect a change here in the meantime; a save that actually changes
   something keeps a version snapshot (see saveCourseChanges()) tagged to
   this request. If the request is later marked Rejected, that snapshot
   is discarded (see discardVersionsForRequest()) rather than kept and
   shown in Version History.
   ============================================================ */

function openChangeRequestsScreen() {
    showScreen("changeRequestsScreen");
    loadChangeRequestsScreen();
}

async function loadChangeRequestsScreen() {
    const user = getCurrentUser();
    if (!user) return;
    document.getElementById("crScreenUserPill").textContent = user.name;
    await pollChangeRequestStatuses();
    renderChangeRequestsList();
}

/* Checks every locally pending request that has a real token against
   the backend, and updates any that the approver has actually
   responded to (via the email Approve/Reject links). This is what
   actually moves a request out of "pending" now — not a button click
   in this screen. */
async function pollChangeRequestStatuses() {
    const requests = getChangeRequestsStore();
    const pendingWithToken = requests.filter(r => r.status === "pending" && r.token);
    if (!pendingWithToken.length) return;

    let changed = false;
    await Promise.all(pendingWithToken.map(async request => {
        try {
            const response = await fetch(`/api/change-requests/${request.token}`, { credentials: "same-origin" });
            if (!response.ok) return;
            const data = await response.json();

            if (data.status === "Approved" || data.status === "Rejected") {
                request.status = data.status.toLowerCase();
                request.reviewedBy = request.coordinatorEmail || "Approver";
                request.reviewedByRole = "Approver (via email)";
                request.reviewedAt = new Date().toISOString();
                if (data.reason) request.reason = data.reason;

                if (request.status === "rejected") {
                    discardVersionsForRequest(request.courseId, request.id);
                }
                changed = true;
            }
        } catch (err) {
            console.error("Could not check change request status:", err);
        }
    }));

    if (changed) saveChangeRequestsStore(requests);
}

async function refreshChangeRequestStatus() {
    await pollChangeRequestStatuses();
    renderChangeRequestsList();
    showToast("Status refreshed");
}

function renderChangeRequestsList() {
    const requests = getChangeRequestsStore();
    const pending = requests.filter(r => r.status === "pending");
    const reviewed = requests
        .filter(r => r.status !== "pending")
        .sort((a, b) => new Date(b.reviewedAt || 0) - new Date(a.reviewedAt || 0))
        .slice(0, 20);

    document.getElementById("crPendingCount").textContent = pending.length;

    const pendingList = document.getElementById("crPendingList");
    if (!pending.length) {
        pendingList.innerHTML = `<div class="cr-queue-empty">No pending change requests right now.</div>`;
    } else {
        pendingList.innerHTML = pending.map(req => {
            const items = changeRequestItems(req);
            const headline = items.length > 1
                ? `${items.length} changes requested`
                : escapeHtml(items[0]?.section || "—");
            const actionButtons = req.token
                ? `
                  <span class="wf-status-pill wf-status-pending">Waiting on ${escapeHtml(req.coordinatorEmail || "approver")}'s email response</span>
                  <button class="btn btn-outline" onclick="refreshChangeRequestStatus()">Check Now</button>
                `
                : `
                  <button class="btn btn-success" onclick="resolveChangeRequest('${req.id}', 'approved')">Mark Approved</button>
                  <button class="btn btn-warning" onclick="resolveChangeRequest('${req.id}', 'rejected')">Mark Rejected</button>
                `;
            return `
              <div class="wf-request-card">
                <div class="wf-request-head">
                  <div>
                    <div class="wf-request-course">${escapeHtml(req.courseCode)} — ${escapeHtml(req.courseName)}</div>
                    <div class="wf-request-section">${headline}${items.length > 1 ? `<span class="wf-request-count-badge">${items.length}</span>` : ""}</div>
                  </div>
                  <div class="wf-request-meta">
                    Requested by ${escapeHtml(req.requestedBy)} (${escapeHtml(req.requestedByRole)})<br>
                    ${formatDateTime(req.createdAt)}
                  </div>
                </div>
                <div class="wf-request-items">
                  ${items.map(it => `
                    <div class="wf-request-item">
                      <div class="wf-request-item-section">${escapeHtml(it.section)}</div>
                      <div class="wf-request-item-details">${escapeHtml(it.details)}</div>
                      ${it.reason ? `<div class="wf-request-item-reason">Reason: ${escapeHtml(it.reason)}</div>` : ""}
                    </div>
                  `).join("")}
                </div>
                <div class="wf-request-actions">
                  <button class="btn btn-primary" onclick="reviewChangeRequest('${req.id}')">Open Unit Outline</button>
                  ${actionButtons}
                </div>
              </div>
            `;
        }).join("");
    }

    const reviewedList = document.getElementById("crReviewedList");
    if (!reviewed.length) {
        reviewedList.innerHTML = `<div class="cr-queue-empty">Nothing resolved yet.</div>`;
    } else {
        reviewedList.innerHTML = reviewed.map(req => {
            const items = changeRequestItems(req);
            const label = items.length > 1 ? `${items.length} changes` : (items[0]?.section || "—");
            return `
              <div class="wf-reviewed-item">
                <span class="wf-status-pill wf-status-${req.status}">${req.status}</span>
                &nbsp; <strong>${escapeHtml(req.courseCode)}</strong> — ${escapeHtml(label)}
                <div class="wf-request-meta" style="margin-top:4px;">
                  Resolved by ${escapeHtml(req.reviewedBy || "—")} on ${formatDateTime(req.reviewedAt)}
                </div>
              </div>
            `;
        }).join("");
    }
}

function reviewChangeRequest(requestId) {
    const request = getChangeRequestsStore().find(r => r.id === requestId);
    if (!request) return;
    if (!request.courseId) {
        showToast("This request isn't linked to a course");
        return;
    }
    // openCourse() clears any stale review tag first, so set this after.
    openCourse(request.courseId);
    setActiveReviewRequest(request);
}

function resolveChangeRequest(requestId, newStatus) {
    // Legacy fallback only — for requests created before real email
    // approval was wired up (no token, see submitChangeRequest()). Any
    // request with a token is resolved for real by the approver
    // clicking Approve/Reject in their email; this button no longer
    // appears for those (see renderChangeRequestsList()).
    const requests = getChangeRequestsStore();
    const request = requests.find(r => r.id === requestId);
    if (!request) return;

    const user = getCurrentUser();
    request.status = newStatus;
    request.reviewedBy = user ? user.name : "Unknown";
    request.reviewedByRole = user ? (roleLabels[user.role] || user.role) : "—";
    request.reviewedAt = new Date().toISOString();

    saveChangeRequestsStore(requests);

    // A rejected request means whatever was applied while reviewing it
    // shouldn't count as a real version of the unit outline — drop any
    // version snapshot that was tagged to this request so it's neither
    // stored nor shown in Version History.
    if (newStatus === "rejected") {
        discardVersionsForRequest(request.courseId, requestId);
    }

    clearActiveReviewRequest();
    renderChangeRequestsList();
    showToast(`Request marked ${newStatus}`);
}

function formatDateTime(isoString) {
    if (!isoString) return "—";
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return "—";
    return date.toLocaleString("en-AU", {
        day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
}

/* ============================================================
   ADMIN — VERSION HISTORY (blended into the Unit Outline nav bar)
   A nav item opens a dropdown listing Current + every previous saved
   version. Clicking one shows the FULL outline as it looked at that
   point (every field, not just what changed), with the field(s) that
   were changed right after that version highlighted, and the form
   locked read-only. Fields changed by applying a Course/Unit
   Coordinator's change request (rather than a direct admin edit) get a
   small * mark alongside the highlight.
   ============================================================ */

// Tracks which historical version (if any) is currently being previewed
// on the Unit Outline screen: { courseId, versionId, label } or null.
let previewingVersion = null;

function versionLabelFor(index) {
    return `Version ${index + 1}.0`;
}

function historyChronological(course) {
    return (course.versionHistory || []).slice().sort((a, b) => new Date(a.savedAt) - new Date(b.savedAt));
}

function diffOutlineData(oldData, newData) {
    const changed = [];
    const keys = new Set([...Object.keys(oldData || {}), ...Object.keys(newData || {})]);
    keys.forEach(key => {
        const a = oldData ? oldData[key] : undefined;
        const b = newData ? newData[key] : undefined;
        if (JSON.stringify(a) !== JSON.stringify(b)) changed.push(key);
    });
    return changed;
}

// Clears every "changed" marking left by a previous preview (the ring
// around the field, the wrapper's accent bar, the "Changed" badge, and
// the inline diff note), so they don't accumulate across versions.
function clearFieldChangeMarks() {
    document.querySelectorAll("#unitScreen .field-changed").forEach(el => el.classList.remove("field-changed"));
    document.querySelectorAll("#unitScreen .changed-wrapper").forEach(el => el.classList.remove("changed-wrapper"));
    document.querySelectorAll("#unitScreen .field-changed-badge").forEach(el => el.remove());
    document.querySelectorAll("#unitScreen .field-diff-note").forEach(el => el.remove());
}

// Renders a field value for display inside the diff note: escapes HTML,
// shows a placeholder for empty values, reads booleans (checkboxes) as
// Checked/Unchecked, and keeps long text readable.
function formatDiffValue(value) {
    if (typeof value === "boolean") return value ? "Checked" : "Unchecked";
    if (value === undefined || value === null || value === "") return "<em>(empty)</em>";
    const text = String(value);
    const escaped = text.replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[ch]));
    return escaped.length > 160 ? escaped.slice(0, 160) + "…" : escaped;
}

// Marks a single field as changed: a strong ring on the field itself, an
// accent bar on its containing box/item, an explicit "Changed" badge
// next to whatever label the field has (a <label>, an LO/Week badge, or
// a checkbox's own <label>), and — on top of that — an inline note
// showing the value this field was changed to afterwards, so the
// difference between the version being previewed and the version that
// replaced it is visible at a glance rather than something the admin
// has to go find.
function markFieldChanged(fieldId, viaRequest, newValue) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    el.classList.add("field-changed");

    const wrapper = el.closest(".field-box, .lo-item, .weekly-item, .checkbox-item");
    if (wrapper) wrapper.classList.add("changed-wrapper");

    const labelHost = wrapper?.querySelector("label, .lo-badge, .week-badge");
    if (labelHost && !labelHost.querySelector(".field-changed-badge")) {
        const badge = document.createElement("span");
        badge.className = "field-changed-badge" + (viaRequest ? " via-request" : "");
        badge.title = viaRequest
            ? "Changed via a Course/Unit Coordinator change request"
            : "Changed right after this version";
        badge.textContent = viaRequest ? "★ Changed" : "Changed";
        labelHost.appendChild(badge);
    }

    if (wrapper && !wrapper.querySelector(".field-diff-note")) {
        // .field-box stacks vertically, so the note can append directly to
        // it. .lo-item / .weekly-item lay their badge and content out as a
        // flex ROW, so the note goes inside the content column (the input's
        // direct parent) instead — appending to the row itself would place
        // it as a third row-item next to the badge rather than beneath the
        // field text. .checkbox-item is also a flex row but has no separate
        // content column to nest into, so the note appends to the row
        // itself and CSS (.checkbox-item.changed-wrapper) wraps it onto
        // its own line.
        const noteHost = (wrapper.classList.contains("field-box") || wrapper.classList.contains("checkbox-item"))
            ? wrapper : el.parentElement;
        const note = document.createElement("div");
        note.className = "field-diff-note";
        note.innerHTML = `<span class="fdn-tag">Later changed to</span><span class="fdn-value">${formatDiffValue(newValue)}</span>`;
        noteHost.appendChild(note);
    }
}

// Positions the floating version-side-panel directly beneath its nav
// trigger, right-aligned to it — since the panel now lives outside the
// nav bar (as a fixed-position element) it needs its coordinates set in
// JS rather than relying on CSS `position:absolute` inside the <li>.
function positionVersionSidePanel() {
    const trigger = document.querySelector("#versionNavItem .version-nav-trigger");
    const panel = document.getElementById("versionSidePanel");
    if (!trigger || !panel) return;
    const rect = trigger.getBoundingClientRect();
    panel.style.top = `${rect.bottom + 4}px`;
    const left = Math.max(8, rect.right - panel.offsetWidth);
    panel.style.left = `${left}px`;
}

function toggleVersionDropdown(event) {
    if (event) event.stopPropagation();
    const item = document.getElementById("versionNavItem");
    const panel = document.getElementById("versionSidePanel");
    const opening = !item.classList.contains("open");
    item.classList.toggle("open", opening);
    panel.classList.toggle("open", opening);
    if (opening) positionVersionSidePanel();
}

// Closes the Version History dropdown on an outside click, and keeps the
// floating panel aligned under its trigger on resize/scroll while open.
document.addEventListener("click", event => {
    const item = document.getElementById("versionNavItem");
    const panel = document.getElementById("versionSidePanel");
    if (item && item.classList.contains("open") &&
        !item.contains(event.target) && panel && !panel.contains(event.target)) {
        item.classList.remove("open");
        panel.classList.remove("open");
    }
});
window.addEventListener("resize", () => {
    if (document.getElementById("versionNavItem")?.classList.contains("open")) {
        positionVersionSidePanel();
    }
});

function renderVersionSidePanel(course) {
    const navItem = document.getElementById("versionNavItem");
    const user = getCurrentUser();

    if (!user || user.role !== "admin") {
        navItem.style.display = "none";
        document.getElementById("versionSidePanel").classList.remove("open");
        return;
    }

    // Always show the nav item for admins (even with zero history yet) so
    // it's a discoverable, working control rather than something that
    // silently appears only after a second save.
    navItem.style.display = "";
    navItem.classList.remove("open");
    document.getElementById("versionSidePanel").classList.remove("open");
    document.getElementById("versionNavCurrentLabel").textContent =
        previewingVersion ? previewingVersion.label : "Version History";

    const history = historyChronological(course);
    const list = document.getElementById("versionSideList");
    // The live/current outline is effectively "the next version" after
    // every saved snapshot in history — e.g. with 1 saved version in
    // history, the current live outline is "Version 2.0".
    const currentLabel = versionLabelFor(history.length);

    const items = [`
      <button class="version-side-item ${!previewingVersion ? "active" : ""}" onclick="showCurrentVersionView()">
        <span class="vsi-label">${currentLabel} (current)</span>
        <span class="vsi-when">Live version</span>
      </button>
    `];

    if (!history.length) {
        items.push(`<div class="vh-empty" style="padding:10px 6px;">No previous versions yet — save a change to start building history.</div>`);
    }

    for (let i = history.length - 1; i >= 0; i--) {
        const v = history[i];
        const isActive = previewingVersion && previewingVersion.versionId === v.id;
        items.push(`
          <button class="version-side-item ${isActive ? "active" : ""}" onclick="previewVersion('${course.id}', '${v.id}')">
            <span class="vsi-label">${versionLabelFor(i)}${v.requestId ? '<span class="vsi-star" title="Followed a change request">*</span>' : ""}</span>
            <span class="vsi-when">${formatDateTime(v.savedAt)}</span>
          </button>
        `);
    }

    list.innerHTML = items.join("");
}

function previewVersion(courseId, versionId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;

    const history = historyChronological(course);
    const index = history.findIndex(v => v.id === versionId);
    if (index === -1) return;

    const version = history[index];
    // What this version looked like right before it was replaced —
    // either by the next saved version, or by what's current now.
    const nextData = (index + 1 < history.length) ? history[index + 1].outlineData : course.outlineData;
    const changedFields = diffOutlineData(version.outlineData, nextData);
    // Whether that next save was applying a change request rather than a
    // direct admin edit — the version snapshot is tagged at save-time.
    const viaChangeRequest = !!version.requestId;

    // Show the ENTIRE outline as it was at this version, not just the
    // changed fields.
    applyOutlineData(version.outlineData);
    document.getElementById("disp_organisation").textContent =
        version.outlineData?.organisation || "Sydney Polytechnic Institute";

    // Lock every field — this is a read-only look back, regardless of
    // the viewer's normal edit permissions.
    document.querySelectorAll("#unitScreen input, #unitScreen textarea, #unitScreen select").forEach(el => {
        el.disabled = true;
    });
    clearFieldChangeMarks();
    changedFields.forEach(fieldId => markFieldChanged(fieldId, viaChangeRequest, nextData[fieldId]));

    previewingVersion = { courseId, versionId, label: versionLabelFor(index) };

    document.getElementById("versionPreviewTitle").textContent = `Viewing ${previewingVersion.label} (read-only)`;
    document.getElementById("versionPreviewMeta").textContent =
        `Saved ${formatDateTime(version.savedAt)} by ${version.savedBy} (${version.savedByRole}) — ${version.note}. `
        + (changedFields.length
            ? `Field(s) marked "Changed" below were updated right after this version${viaChangeRequest ? " (★ = via a change request)" : ""}.`
            : `No fields changed after this version.`);
    document.getElementById("versionPreviewBanner").style.display = "flex";

    const saveBtn = document.getElementById("saveOutlineBtn");
    if (saveBtn) saveBtn.style.display = "none";

    renderVersionSidePanel(course);
}

function showCurrentVersionView() {
    const active = JSON.parse(localStorage.getItem("spi_active_course") || "null");
    if (!active) return;
    const course = getCoursesStore().find(c => c.id === active.id);
    if (!course) return;

    applyOutlineData(course.outlineData);
    document.getElementById("disp_organisation").textContent =
        course.outlineData?.organisation || "Sydney Polytechnic Institute";

    clearFieldChangeMarks();

    previewingVersion = null;
    document.getElementById("versionPreviewBanner").style.display = "none";

    const saveBtn = document.getElementById("saveOutlineBtn");
    if (saveBtn) saveBtn.style.display = "";

    // Restores the correct disabled/enabled state for the current role
    // (previewVersion() force-disabled every field above).
    updateRolePermissions();

    renderVersionSidePanel(course);
}

function restoreVersionFromPreview() {
    if (!previewingVersion) return;
    const { courseId, versionId, label } = previewingVersion;

    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;
    const version = (course.versionHistory || []).find(v => v.id === versionId);
    if (!version) return;

    if (!confirm(`Restore ${label} (saved ${formatDateTime(version.savedAt)}) as the current version? The current version will itself be kept in history.`)) return;

    clearActiveReviewRequest();
    saveCourseChanges(courseId, version.outlineData, `Restored to ${label} (originally saved ${formatDateTime(version.savedAt)})`);

    showCurrentVersionView();
    showToast(`${label} restored as the current version`);
}

// Removes any version snapshot(s) tagged to a change request — used when
// that request is rejected, so a rejected change is never stored or
// shown as a version of the unit outline.
function discardVersionsForRequest(courseId, requestId) {
    if (!courseId || !requestId) return;
    const courses = getCoursesStore();
    const index = courses.findIndex(c => c.id === courseId);
    if (index === -1 || !courses[index].versionHistory) return;

    const before = courses[index].versionHistory.length;
    courses[index].versionHistory = courses[index].versionHistory.filter(v => v.requestId !== requestId);
    if (courses[index].versionHistory.length !== before) {
        setCoursesStore(courses);
    }
}

async function addCourse(courseData) {
    const response = await fetch("/dashboard/api/courses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(courseData),
    });
    if (!response.ok) {
        throw new Error(`Server responded ${response.status} ${response.statusText}`);
    }
    const created = await response.json();
    await syncCoursesFromBackend();
    loadDashboard();
    showToast("Course added successfully");
    return created;
}

async function deleteCourse(courseId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;

    if (!confirm(`Delete ${course.code} — ${course.name}?`)) return;

    try {
        const response = await fetch(`/dashboard/api/courses/${courseId}`, {
            method: "DELETE",
            credentials: "same-origin",
        });
        if (!response.ok) {
            throw new Error(`Server responded ${response.status} ${response.statusText}`);
        }
        await syncCoursesFromBackend();
        loadDashboard();
        showToast("Course deleted");
    } catch (err) {
        console.error("Could not delete course:", err);
        showToast("Could not delete the course — check the server is running");
    }
}

function openCourse(courseId) {
    const course = getCoursesStore().find(c => c.id === courseId);
    if (!course) return;

    // Clear any leftover "reviewing a change request" tag from a previous
    // visit — reviewChangeRequest() re-sets it right after calling this,
    // so a normal "Open Outline" click never inherits a stale one.
    clearActiveReviewRequest();

    localStorage.setItem("spi_active_course", JSON.stringify(course));
    showScreen("unitScreen");

    // Load this course's actual saved outline data into every field
    // (falling back to the sample template for a brand-new course).
    applyOutlineData(course.outlineData);

    // Header fields that live outside the field-permission system.
    document.getElementById("unit_code").value = course.outlineData?.unit_code || course.code;
    document.getElementById("title").value = course.outlineData?.title || course.name;
    document.getElementById("disp_organisation").textContent =
        course.outlineData?.organisation || "Sydney Polytechnic Institute";

    const user = getCurrentUser();
    if (user) {
        document.getElementById("unitUserPill").textContent = `${user.name} — ${roleLabels[user.role] || user.role}`;
    }

    updateRolePermissions();

    // Always open on the current (live, editable) version — reset any
    // leftover preview state from a previous course visit.
    previewingVersion = null;
    document.getElementById("versionPreviewBanner").style.display = "none";
    const saveBtn = document.getElementById("saveOutlineBtn");
    if (saveBtn) saveBtn.style.display = "";
    renderVersionSidePanel(course);

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
        if (!el.matches("input, textarea, select")) return;
        if (el.type === "checkbox") {
            data[el.id] = el.checked;
        } else {
            data[el.id] = el.value;
        }
    });

    return data;
}

/* The HTML ships with sample content already filled into the Unit
   Outline fields (used as the starting template for a brand-new course).
   We snapshot that pristine state once, before anything else touches the
   DOM, so we can reliably reset back to it — otherwise switching between
   courses would leak one course's edited values into another course's
   form, since the fields are just shared DOM elements. */
let templateDefaults = null;

function captureTemplateDefaults() {
    templateDefaults = collectOutlineData();
}

function resetOutlineFields() {
    document.querySelectorAll("#unitScreen [id]").forEach(el => {
        if (!el.id || !el.matches("input, textarea, select")) return;
        const fallback = templateDefaults ? templateDefaults[el.id] : undefined;

        if (el.type === "checkbox") {
            el.checked = !!fallback;
        } else if (el.tagName === "SELECT") {
            el.value = fallback ?? el.options[0]?.value ?? "";
        } else {
            el.value = fallback ?? "";
        }
    });
}

/* Populates the Unit Outline form for the course currently being opened:
   resets every field to the template default first, then overlays
   whatever this specific course has actually saved — so a brand-new
   course shows the sample template, and a previously-saved course shows
   exactly what was saved for it (not leftovers from another course). */
function applyOutlineData(data) {
    resetOutlineFields();

    if (data) {
        document.querySelectorAll("#unitScreen [id]").forEach(el => {
            if (!el.id || !el.matches("input, textarea, select")) return;
            if (!(el.id in data)) return;

            if (el.type === "checkbox") {
                el.checked = !!data[el.id];
            } else {
                el.value = data[el.id] ?? "";
            }
        });
    }

    calculateTotalHours();
    checkAssessmentTotal();
    initAutoGrowTextareas();
}

function saveCourseChanges(courseId, outlineData, noteOverride) {
    const courses = getCoursesStore();
    const index = courses.findIndex(c => c.id === courseId);
    if (index === -1) return false;

    // Snapshot the outgoing version (before this save overwrites it) so
    // admins can browse previous versions later. Skipped on a course's
    // very first save (no prior version yet to keep) and skipped when
    // nothing actually changed, so a no-op save never clutters history.
    const previous = courses[index].outlineData;
    const changedFromPrevious = previous && diffOutlineData(previous, outlineData).length > 0;
    if (changedFromPrevious) {
        if (!courses[index].versionHistory) courses[index].versionHistory = [];

        const user = getCurrentUser();
        const activeReview = getActiveReviewRequest();
        const note = noteOverride || (activeReview
            ? `Applied via change request — ${summarizeChangeRequestItems(activeReview.items)}`
            : `Direct save by ${user ? user.name : "Unknown"} (${user ? (roleLabels[user.role] || user.role) : "—"})`);

        courses[index].versionHistory.push({
            id: "ver-" + Date.now() + "-" + Math.random().toString(16).slice(2),
            savedAt: new Date().toISOString(),
            savedBy: user ? user.name : "Unknown",
            savedByRole: user ? (roleLabels[user.role] || user.role) : "—",
            note,
            // Tags this snapshot to the change request being applied (if
            // any), so it can be found and discarded later if that
            // request ends up rejected — see discardVersionsForRequest().
            requestId: activeReview ? activeReview.id : null,
            outlineData: previous
        });
    }

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

/* Tracks which pending change request (if any) an Administrator is
   currently working on when they open a unit outline from the Change
   Requests screen, so the next Save Outline Changes gets tagged with
   that request instead of showing up as an anonymous "direct save". */
function getActiveReviewRequest() {
    return JSON.parse(localStorage.getItem("spi_active_review_request") || "null");
}

function setActiveReviewRequest(request) {
    localStorage.setItem("spi_active_review_request", JSON.stringify({
        id: request.id,
        items: changeRequestItems(request),
        requestedBy: request.requestedBy
    }));
}

function clearActiveReviewRequest() {
    localStorage.removeItem("spi_active_review_request");
}

function saveChanges() {
    // Fields stay readable via .value even while disabled, so guard
    // against accidentally saving a previewed historical version over
    // the real current data.
    if (previewingVersion) {
        showToast("You're viewing a previous version (read-only) — return to Current to make edits.");
        return;
    }

    const orgName = document.getElementById("organisation").value;
    document.getElementById("disp_organisation").innerText = orgName;

    const active = JSON.parse(localStorage.getItem("spi_active_course") || "null");
    if (active) {
        saveCourseChanges(active.id, collectOutlineData());
        const refreshed = getCoursesStore().find(c => c.id === active.id);
        if (refreshed) renderVersionSidePanel(refreshed);
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
    // NOTE: since syncCoursesFromBackend() now rebuilds the local
    // course list from the server on every dashboard load, anything
    // imported here that isn't ALSO a real course in the backend will
    // disappear again the next time the dashboard refreshes. This
    // still only touches localStorage — it was out of scope to also
    // wire up a real bulk-import backend endpoint this pass.
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
    // Exit preview mode first (back to the real current data) so the
    // save below is never accidentally skipped or applied to stale data.
    if (previewingVersion) {
        showCurrentVersionView();
    }

    saveChanges();

    // If an Administrator opened this outline from the Change Requests
    // screen (to reflect a change there), take them back to that list
    // instead of the main dashboard, so it's easy to mark the request
    // resolved next. The request itself stays pending until they do.
    if (getActiveReviewRequest()) {
        showScreen("changeRequestsScreen");
        loadChangeRequestsScreen();
        return;
    }

    goToHomeScreen();
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
    captureTemplateDefaults();
    getCoursesStore();
    freshStartVersionHistory();
    checkAuthSession();
    calculateTotalHours();
    checkAssessmentTotal();
    updateRolePermissions();
});

/* ============================================================
   BACKEND CONNECTION  (Python  <-->  JavaScript)

   This is the whole frontend/backend workflow:

     unit.py      defines the Unit class + get_all_units()
     server.py    turns those objects into JSON at GET /api/units
     script.js    fetch()es that URL and parses the JSON
     index_1.html displays the result

   Python and JavaScript never "convert" into each other. Python
   serialises to JSON text; JavaScript parses that JSON text. HTTP
   is the only thing the two languages share.
   ============================================================ */

/* Where the Python backend lives.

   If this page was served BY server.py (http://127.0.0.1:5000/...),
   a relative URL works and there is no cross-origin request.

   If you opened index_1.html some other way -- double-clicked it
   (file://) or used VS Code Live Server (port 5500) -- a relative URL
   would point at the wrong place, so fall back to the absolute
   address of the Flask server. That IS a cross-origin request, which
   is why server.py enables CORS. */
const BACKEND_ORIGIN = "http://127.0.0.1:5000";

function backendUrl(path) {
    const servedByFlask =
        window.location.protocol.startsWith("http") &&
        window.location.port === "5000";
    return servedByFlask ? path : BACKEND_ORIGIN + path;
}

const BACKEND_URL = backendUrl("/api/units");

async function loadUnitsFromBackend() {
    const statusEl = document.getElementById("backendStatus");
    const bodyEl = document.getElementById("backendUnitsBody");
    if (!statusEl || !bodyEl) return;

    statusEl.textContent = "Loading from backend...";
    statusEl.className = "backend-status";
    bodyEl.innerHTML = "";

    try {
        // 1. Ask the Python server for the data.
        const response = await fetch(BACKEND_URL);

        // fetch() does NOT throw on 404/500 -- it only throws if the
        // request could not be made at all. Check response.ok yourself.
        if (!response.ok) {
            throw new Error(`Server responded ${response.status} ${response.statusText}`);
        }

        // 2. Parse the JSON body into real JavaScript objects.
        const data = await response.json();

        // 3. Turn the plain objects into Unit instances (unit.js).
        const units = data.map(row => new Unit(row.unit_code, row.unit_name));

        // 4. Render them into the table.
        renderBackendUnits(units);

        statusEl.textContent = `Loaded ${units.length} unit(s) from Python at ${BACKEND_URL}`;
        statusEl.className = "backend-status ok";
    } catch (err) {
        // Most common cause: server.py isn't running.
        statusEl.textContent =
            `Could not reach ${BACKEND_URL} -- ${err.message}. ` +
            `Check that server.py is running (you should see ` +
            `"Running on http://127.0.0.1:5000" in its terminal).`;
        statusEl.className = "backend-status error";
        console.error("[backend] fetch failed for", BACKEND_URL, err);
        console.error("[backend] this page was loaded from:", window.location.href);
    }
}

function renderBackendUnits(units) {
    const bodyEl = document.getElementById("backendUnitsBody");
    bodyEl.innerHTML = "";

    units.forEach(unit => {
        const info = unit.getCode();   // {unit_code, unit_name} -- same shape as unit.py
        const tr = document.createElement("tr");

        const codeCell = document.createElement("td");
        codeCell.textContent = info.unit_code;
        codeCell.className = "backend-code";

        const nameCell = document.createElement("td");
        nameCell.textContent = info.unit_name;

        tr.appendChild(codeCell);
        tr.appendChild(nameCell);
        bodyEl.appendChild(tr);
    });
}
