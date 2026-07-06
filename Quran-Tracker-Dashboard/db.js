/**
 * db.js — Data layer for Quran Memorization Tracker
 * Reads/writes via Flask API backend. No GitHub dependency.
 */

// Set API_BASE via query param ?api=https://your-app.onrender.com
// Defaults to same-origin (empty string)
const API_BASE = new URLSearchParams(window.location.search).get('api') || '';

let AUTH_TOKEN = localStorage.getItem('quran_api_token') || '';

function setToken(token) {
  AUTH_TOKEN = token;
  localStorage.setItem('quran_api_token', token);
}

function clearToken() {
  AUTH_TOKEN = '';
  localStorage.removeItem('quran_api_token');
}

function apiHeaders() {
  const h = { 'Content-Type': 'application/json' };
  if (AUTH_TOKEN) h['Authorization'] = `Bearer ${AUTH_TOKEN}`;
  return h;
}

// ─── Auth ───

async function apiLogin(username, password) {
  const res = await fetch(API_BASE + '/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error('فشل تسجيل الدخول');
  const data = await res.json();
  setToken(data.token);
  return data.user;
}

// ─── Core: load full data ───

async function loadData() {
  const res = await fetch(API_BASE + '/api/data' + '?t=' + Date.now());
  if (!res.ok) throw new Error('Failed to load data');
  return res.json();
}

// ─── Queries (client-side on loaded data) ───

function getStudentById(data, id) {
  return data.students.find(s => s.id === id);
}

function getTeamById(data, id) {
  return data.teams.find(t => t.id === id);
}

function getSessionById(data, id) {
  return data.sessions.find(s => s.id === id);
}

function getStudentsByTeam(data, teamId) {
  return data.students.filter(s => s.team_id === teamId);
}

function getEntriesForSession(data, sessionId) {
  return data.entries.filter(e => e.session_id === sessionId);
}

function getEntry(data, studentId, sessionId) {
  return data.entries.find(e => e.student_id === studentId && e.session_id === sessionId);
}

function getSessionTeamTotals(data, sessionId) {
  const entries = getEntriesForSession(data, sessionId);
  const totals = {};
  for (const t of data.teams) {
    totals[t.id] = { team_name: t.name, total_hifdh: 0, total_tilawah: 0, total_rabt: 0, total_points: 0, student_count: 0 };
  }
  for (const e of entries) {
    const s = getStudentById(data, e.student_id);
    if (!s) continue;
    const tid = s.team_id;
    if (!totals[tid]) continue;
    totals[tid].total_hifdh += e.hifdh_pages;
    totals[tid].total_tilawah += e.tilawah_pages;
    totals[tid].total_rabt += e.rabt_pages;
    totals[tid].total_points += e.points;
  }
  for (const s of data.students) {
    if (totals[s.team_id]) totals[s.team_id].student_count++;
  }
  return Object.values(totals).sort((a, b) => b.total_points - a.total_points);
}

function getCumulativeTeamTotals(data) {
  const totals = {};
  for (const t of data.teams) {
    totals[t.id] = { team_name: t.name, total_hifdh: 0, total_tilawah: 0, total_rabt: 0, total_points: 0 };
  }
  for (const e of data.entries) {
    const s = getStudentById(data, e.student_id);
    if (!s) continue;
    const tid = s.team_id;
    if (!totals[tid]) continue;
    totals[tid].total_hifdh += e.hifdh_pages;
    totals[tid].total_tilawah += e.tilawah_pages;
    totals[tid].total_rabt += e.rabt_pages;
    totals[tid].total_points += e.points;
  }
  return Object.values(totals).sort((a, b) => b.total_points - a.total_points);
}

function getCumulativeHistory(data) {
  const sessions = [...data.sessions].sort((a, b) => a.id - b.id);
  const teams = data.teams;
  const history = [];
  for (const session of sessions) {
    const entries = getEntriesForSession(data, session.id);
    for (const team of teams) {
      const teamStudents = new Set(getStudentsByTeam(data, team.id).map(s => s.id));
      let sessionHifdh = 0, sessionPoints = 0;
      for (const e of entries) {
        if (teamStudents.has(e.student_id)) {
          sessionHifdh += e.hifdh_pages;
          sessionPoints += e.points;
        }
      }
      history.push({
        session_id: session.id, date: session.date, label: session.label,
        team_name: team.name, session_hifdh: sessionHifdh, session_points: sessionPoints
      });
    }
  }
  const cumMap = {};
  for (const h of history) {
    const key = h.team_name;
    if (!cumMap[key]) cumMap[key] = 0;
    cumMap[key] += h.session_hifdh;
    h.cumulative_hifdh = cumMap[key];
  }
  return history;
}

function getTopMemorizers(data, sessionId) {
  const entries = getEntriesForSession(data, sessionId).filter(e => e.hifdh_pages > 0);
  const result = entries.map(e => {
    const s = getStudentById(data, e.student_id);
    const t = s ? getTeamById(data, s.team_id) : null;
    return {
      student_name: s ? s.name : '?',
      team_name: t ? t.name : '?',
      hifdh_pages: e.hifdh_pages,
      tilawah_pages: e.tilawah_pages,
      rabt_pages: e.rabt_pages,
      points: e.points
    };
  });
  result.sort((a, b) => b.hifdh_pages - a.hifdh_pages);
  return result;
}

// ─── API Mutations ───

async function apiSaveEntry(studentId, sessionId, hifdh, tilawah, rabt, points, notes) {
  const res = await fetch(API_BASE + '/api/entries', {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({
      student_id: studentId, session_id: sessionId,
      hifdh_pages: hifdh, tilawah_pages: tilawah,
      rabt_pages: rabt, points, notes,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Save failed');
  }
  return res.json();
}

async function apiAddStudent(name, teamId) {
  const res = await fetch(API_BASE + '/api/students', {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ name, team_id: teamId }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Failed to add student');
  }
  return res.json();
}

async function apiRemoveStudent(studentId) {
  const res = await fetch(API_BASE + '/api/students/' + studentId, {
    method: 'DELETE',
    headers: apiHeaders(),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Failed to remove student');
  }
  return res.json();
}

async function apiAddTeam(name) {
  const res = await fetch(API_BASE + '/api/teams', {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Failed to add team');
  }
  return res.json();
}

async function apiAddSession(label, date) {
  const res = await fetch(API_BASE + '/api/sessions', {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ label, date }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Failed to add session');
  }
  return res.json();
}
