/* ============================================================
   Unit — JavaScript translation of unit.py

   Loaded BEFORE script.js in index_1.html so `Unit` exists when
   script.js runs.

   Note: the app's course objects already carry `code` and `name`
   (see defaultCourses in script.js). This class doesn't replace
   that store -- it wraps a course when you need unit-shaped data,
   e.g. for export or for a JSON payload.
   ============================================================ */

class Unit {
    constructor(unitCode, unitName) {
        this.code = unitCode;
        this.name = unitName;
    }

    /* Python: get_code() -> dict */
    getCode() {
        return { unit_code: this.code, unit_name: this.name };
    }

    /* Python: to_json() -> str
       JSON.stringify is the JS equivalent of json.dumps. */
    toJson() {
        return JSON.stringify(this.getCode());
    }

    /* Build a Unit from one of the app's existing course objects,
       so there's a single source of truth for the data. */
    static fromCourse(course) {
        return new Unit(course.code, course.name);
    }

    /* Build Units from the whole course store. */
    static fromCourses(courses) {
        return courses.map(Unit.fromCourse);
    }
}
