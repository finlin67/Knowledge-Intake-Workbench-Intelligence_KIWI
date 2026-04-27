import fs from 'node:fs'
import path from 'node:path'
import initSqlJs, { Database } from 'sql.js'
import { FileRecord, Project, TriageSummary } from '@/types'

type DbContext = { dbPath: string; db: Database }
let _db: Database | null = null
let _dbPath = ''

const toProject = (row: any): Project => ({
  id: row.id,
  name: row.name,
  sourceFolder: row.source_folder,
  outputFolder: row.output_folder,
  exportProfile: row.export_profile,
  status: row.status,
  createdAt: row.created_at,
  updatedAt: row.updated_at
})

const toFile = (row: any): FileRecord => ({
  id: row.id,
  projectId: row.project_id,
  filename: row.filename,
  filepath: row.filepath,
  fileSize: row.file_size,
  fileExt: row.file_ext ?? '',
  nextStage: row.next_stage,
  status: row.status,
  workspace: row.workspace,
  subfolder: row.subfolder,
  matchedBy: row.matched_by,
  confidence: row.confidence,
  priority: row.priority,
  signals: row.signals,
  createdAt: row.created_at,
  updatedAt: row.updated_at
})

const schemaSql = `
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  source_folder TEXT NOT NULL,
  output_folder TEXT NOT NULL,
  export_profile TEXT DEFAULT 'anythingllm',
  status TEXT DEFAULT 'idle',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  filepath TEXT NOT NULL,
  file_size INTEGER DEFAULT 0,
  file_ext TEXT,
  next_stage TEXT DEFAULT 'classify',
  status TEXT DEFAULT 'new',
  workspace TEXT DEFAULT 'unassigned',
  subfolder TEXT DEFAULT '',
  matched_by TEXT DEFAULT 'fallback',
  confidence REAL DEFAULT 0.0,
  priority TEXT DEFAULT 'High',
  signals TEXT DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(project_id, workspace);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(project_id, status);
`

async function getDb(outputFolder: string): Promise<Database> {
  const dbDir = path.join(outputFolder, '.kiw')
  const dbPath = path.join(dbDir, 'kiwi.db')

  if (_db && _dbPath === dbPath) return _db

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true })
  }

  const SQL = await initSqlJs()

  if (fs.existsSync(dbPath)) {
    const fileBuffer = fs.readFileSync(dbPath)
    _db = new SQL.Database(fileBuffer)
  } else {
    _db = new SQL.Database()
  }

  _dbPath = dbPath
  initSchema(_db)
  saveDb(_db, dbPath)
  return _db
}

const getActiveDb = async (): Promise<DbContext> => {
  if (!_db || !_dbPath) throw new Error('Database is not initialized')
  return { db: _db, dbPath: _dbPath }
}

function saveDb(db: Database, dbPath: string): void {
  const data = db.export()
  const buffer = Buffer.from(data)
  fs.writeFileSync(dbPath, buffer)
}

function initSchema(db: Database): void {
  db.run(schemaSql)
}

function queryAll(db: Database, sql: string, params: any[] = []): any[] {
  const stmt = db.prepare(sql)
  stmt.bind(params)
  const rows: any[] = []
  while (stmt.step()) {
    rows.push(stmt.getAsObject())
  }
  stmt.free()
  return rows
}

function queryOne(db: Database, sql: string, params: any[] = []): any | null {
  const rows = queryAll(db, sql, params)
  return rows[0] || null
}

function run(db: Database, sql: string, params: any[] = []): void {
  const stmt = db.prepare(sql)
  stmt.run(params)
  stmt.free()
}

export const ensureDbInitialized = async (outputFolder: string): Promise<DbContext> => {
  const db = await getDb(outputFolder)
  return { dbPath: _dbPath, db }
}

export const useDbPath = async (dbPath: string): Promise<void> => {
  const outputFolder = path.dirname(path.dirname(dbPath))
  await getDb(outputFolder)
}

export const createProject = async (data: {
  name: string
  sourceFolder: string
  outputFolder: string
  exportProfile: Project['exportProfile']
}): Promise<Project> => {
  const { db, dbPath } = await ensureDbInitialized(data.outputFolder)
  run(
    db,
    `
    INSERT INTO projects (name, source_folder, output_folder, export_profile, status)
    VALUES (?, ?, ?, ?, 'idle')
  `,
    [data.name, data.sourceFolder, data.outputFolder, data.exportProfile]
  )
  const id = (db as any).exec('SELECT last_insert_rowid() as id')[0].values[0][0] as number
  const row = queryOne(db, 'SELECT * FROM projects WHERE id = ?', [id])
  saveDb(db, dbPath)
  if (!row) throw new Error('Failed to create project')
  return toProject(row)
}

export const getProject = async (id: number): Promise<Project | null> => {
  const { db } = await getActiveDb()
  const row = queryOne(db, 'SELECT * FROM projects WHERE id = ?', [id])
  return row ? toProject(row) : null
}

export const getLastProject = async (): Promise<Project | null> => {
  const { db } = await getActiveDb()
  const row = queryOne(db, 'SELECT * FROM projects ORDER BY id DESC LIMIT 1')
  return row ? toProject(row) : null
}

export const getProjectStats = async (id: number): Promise<{
  total: number
  classified: number
  unassigned: number
  exported: number
  failed: number
}> => {
  const { db } = await getActiveDb()
  const total = Number(queryOne(db, 'SELECT COUNT(*) as count FROM files WHERE project_id = ?', [id])?.count ?? 0)
  const unassigned = Number(
    queryOne(db, 'SELECT COUNT(*) as count FROM files WHERE project_id = ? AND workspace = ?', [id, 'unassigned'])?.count ?? 0
  )
  const exported = Number(
    queryOne(db, 'SELECT COUNT(*) as count FROM files WHERE project_id = ? AND status = ?', [id, 'exported'])?.count ?? 0
  )
  const failed = Number(queryOne(db, 'SELECT COUNT(*) as count FROM files WHERE project_id = ? AND status = ?', [id, 'failed'])?.count ?? 0)
  return { total, classified: total - unassigned, unassigned, exported, failed }
}

export const insertFile = async (data: Omit<FileRecord, 'id' | 'createdAt' | 'updatedAt'>): Promise<FileRecord> => {
  const { db, dbPath } = await getActiveDb()
  run(
    db,
    `
    INSERT INTO files (
      project_id, filename, filepath, file_size, file_ext, next_stage, status, workspace,
      subfolder, matched_by, confidence, priority, signals
    ) VALUES (
      ?, ?, ?, ?, ?, ?, ?, ?,
      ?, ?, ?, ?, ?
    )
  `,
    [
      data.projectId,
      data.filename,
      data.filepath,
      data.fileSize,
      data.fileExt,
      data.nextStage,
      data.status,
      data.workspace,
      data.subfolder,
      data.matchedBy,
      data.confidence,
      data.priority,
      data.signals
    ]
  )
  const id = (db as any).exec('SELECT last_insert_rowid() as id')[0].values[0][0] as number
  const row = queryOne(db, 'SELECT * FROM files WHERE id = ?', [id])
  saveDb(db, dbPath)
  if (!row) throw new Error('Failed to insert file')
  return toFile(row)
}

export const getFiles = (
  projectId: number,
  filters: { status?: string; workspace?: string; search?: string; limit?: number; offset?: number; sort?: string } = {}
): Promise<{ files: FileRecord[]; total: number }> => {
  return (async () => {
    const { db } = await getActiveDb()
    const where: string[] = ['project_id = ?']
    const params: any[] = [projectId]

    if (filters.status) {
      where.push('status = ?')
      params.push(filters.status)
    }
    if (filters.workspace) {
      where.push('workspace = ?')
      params.push(filters.workspace)
    }
    if (filters.search) {
      where.push('(filename LIKE ? OR filepath LIKE ?)')
      params.push(`%${filters.search}%`, `%${filters.search}%`)
    }

    const whereClause = `WHERE ${where.join(' AND ')}`
    const total = Number(queryOne(db, `SELECT COUNT(*) as count FROM files ${whereClause}`, params)?.count ?? 0)
    const orderBy = filters.sort ? filters.sort : 'updated_at DESC'
    const limit = filters.limit ?? 100
    const offset = filters.offset ?? 0
    const rows = queryAll(
      db,
      `SELECT * FROM files ${whereClause} ORDER BY ${orderBy} LIMIT ? OFFSET ?`,
      [...params, limit, offset]
    )
    return { files: rows.map(toFile), total }
  })()
}

export const updateFileWorkspace = async (ids: number[], workspace: string, subfolder: string): Promise<number> => {
  const { db, dbPath } = await getActiveDb()
  let updated = 0
  for (const id of ids) {
    run(
      db,
      `
      UPDATE files SET workspace = ?, subfolder = ?, matched_by = 'manual', updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `,
      [workspace, subfolder, id]
    )
    const changes = Number(queryOne(db, 'SELECT changes() as count')?.count ?? 0)
    updated += changes
  }
  saveDb(db, dbPath)
  return updated
}

export const updateFileStatus = async (id: number, status: FileRecord['status']): Promise<void> => {
  const { db, dbPath } = await getActiveDb()
  run(db, 'UPDATE files SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', [status, id])
  saveDb(db, dbPath)
}

export const getTriageSummary = async (projectId: number): Promise<TriageSummary> => {
  const { db } = await getActiveDb()
  const files = queryAll(
    db,
    "SELECT * FROM files WHERE project_id = ? AND (workspace = 'unassigned' OR status = 'review') ORDER BY updated_at DESC",
    [projectId]
  ).map(toFile)
  const totalUnassigned = files.filter((f) => f.workspace === 'unassigned').length
  const ruleGaps = files.filter((f) => f.matchedBy === 'fallback').length
  const highPriority = files.filter((f) => f.priority === 'High').length
  const aiSessions = files.filter((f) => f.matchedBy === 'ai').length
  const safeToSkip = files.filter((f) => f.fileSize < 1024).length
  return { totalUnassigned, ruleGaps, highPriority, aiSessions, safeToSkip, files }
}
