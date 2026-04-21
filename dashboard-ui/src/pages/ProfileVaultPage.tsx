import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'
import type { CandidateProfile, CandidateSkill, ProfileAssetKind, ProfileVault } from '../types'

const defaultProfile: CandidateProfile = {
  profile_id: 'primary-candidate',
  display_name: 'Primary Candidate',
  headline: 'Senior .NET / AI workflow engineer',
  work_authorization: '',
  preferred_locations: [],
  salary_floor: 0,
  languages: [],
  education: [],
  experience_summary: '',
  skills: [],
  achievements: [],
}

export function ProfileVaultPage() {
  const [vault, setVault] = useState<ProfileVault | null>(null)
  const [profile, setProfile] = useState<CandidateProfile>(defaultProfile)
  const [languagesInput, setLanguagesInput] = useState('')
  const [locationsInput, setLocationsInput] = useState('')
  const [educationInput, setEducationInput] = useState('')
  const [achievementsInput, setAchievementsInput] = useState('')
  const [assetKind, setAssetKind] = useState<ProfileAssetKind>('cv')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    async function loadVault() {
      try {
        const nextVault = await api.getProfileVault()
        if (!isMounted) {
          return
        }
        hydrateVault(nextVault)
      } catch (loadError) {
        if (isMounted) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load profile vault.')
        }
      }
    }

    loadVault()
    return () => {
      isMounted = false
    }
  }, [])

  function hydrateVault(nextVault: ProfileVault) {
    setVault(nextVault)
    setProfile(nextVault.profile)
    setLanguagesInput(nextVault.profile.languages.join(', '))
    setLocationsInput(nextVault.profile.preferred_locations.join('\n'))
    setEducationInput(nextVault.profile.education.join('\n'))
    setAchievementsInput(nextVault.profile.achievements.join('\n'))
  }

  function updateProfile<K extends keyof CandidateProfile>(field: K, value: CandidateProfile[K]) {
    setProfile((current) => ({ ...current, [field]: value }))
  }

  function updateSkill(index: number, field: keyof CandidateSkill, value: string) {
    setProfile((current) => {
      const skills = [...current.skills]
      const nextSkill = { ...skills[index] }
      if (field === 'years' || field === 'confidence') {
        nextSkill[field] = Number(value) as never
      } else {
        nextSkill[field] = value as never
      }
      skills[index] = nextSkill
      return { ...current, skills }
    })
  }

  function addSkill() {
    setProfile((current) => ({
      ...current,
      skills: [...current.skills, { name: '', years: 0, confidence: 1, evidence: '' }],
    }))
  }

  function removeSkill(index: number) {
    setProfile((current) => ({
      ...current,
      skills: current.skills.filter((_, currentIndex) => currentIndex !== index),
    }))
  }

  async function handleSave() {
    try {
      setSaving(true)
      setError(null)
      setMessage(null)
      const nextProfile: CandidateProfile = {
        ...profile,
        languages: parseInlineList(languagesInput),
        preferred_locations: parseLineList(locationsInput),
        education: parseLineList(educationInput),
        achievements: parseLineList(achievementsInput),
        salary_floor: Number(profile.salary_floor) || 0,
        skills: profile.skills
          .map((skill) => ({
            ...skill,
            name: skill.name.trim(),
            evidence: skill.evidence.trim(),
            years: Number(skill.years) || 0,
            confidence: Number(skill.confidence) || 0,
          }))
          .filter((skill) => skill.name),
      }

      const nextVault = await api.saveProfile(nextProfile)
      hydrateVault(nextVault)
      setMessage('Profile vault updated.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save profile.')
    } finally {
      setSaving(false)
    }
  }

  async function handleUpload() {
    if (!uploadFile) {
      setError('Choose a file before uploading.')
      return
    }

    try {
      setUploading(true)
      setError(null)
      setMessage(null)
      const nextVault = await api.uploadProfileAsset(uploadFile, assetKind)
      hydrateVault(nextVault)
      setUploadFile(null)
      setMessage(`${uploadFile.name} uploaded into the vault.`)
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Unable to upload asset.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page-grid">
      <section className="page-main">
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Structured profile</p>
              <h3>Candidate identity and match inputs</h3>
            </div>
            <button className="primary-button" type="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
          </div>

          {message ? <p className="success-banner">{message}</p> : null}
          {error ? <p className="error-banner">{error}</p> : null}

          <div className="form-grid">
            <label className="field">
              <span>Profile id</span>
              <input value={profile.profile_id} onChange={(event) => updateProfile('profile_id', event.target.value)} />
            </label>
            <label className="field">
              <span>Display name</span>
              <input value={profile.display_name} onChange={(event) => updateProfile('display_name', event.target.value)} />
            </label>
            <label className="field field-wide">
              <span>Headline</span>
              <input value={profile.headline} onChange={(event) => updateProfile('headline', event.target.value)} />
            </label>
            <label className="field field-wide">
              <span>Work authorization</span>
              <input
                value={profile.work_authorization}
                onChange={(event) => updateProfile('work_authorization', event.target.value)}
              />
            </label>
            <label className="field">
              <span>Salary floor</span>
              <input
                type="number"
                value={profile.salary_floor}
                onChange={(event) => updateProfile('salary_floor', Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Languages</span>
              <input value={languagesInput} onChange={(event) => setLanguagesInput(event.target.value)} />
            </label>
            <label className="field field-wide">
              <span>Experience summary</span>
              <textarea
                rows={5}
                value={profile.experience_summary}
                onChange={(event) => updateProfile('experience_summary', event.target.value)}
              />
            </label>
            <label className="field">
              <span>Preferred locations</span>
              <textarea rows={5} value={locationsInput} onChange={(event) => setLocationsInput(event.target.value)} />
            </label>
            <label className="field">
              <span>Education</span>
              <textarea rows={5} value={educationInput} onChange={(event) => setEducationInput(event.target.value)} />
            </label>
            <label className="field field-wide">
              <span>Achievements</span>
              <textarea rows={5} value={achievementsInput} onChange={(event) => setAchievementsInput(event.target.value)} />
            </label>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Skills matrix</p>
              <h3>Evidence the matcher can score against</h3>
            </div>
            <button className="ghost-button" type="button" onClick={addSkill}>
              Add skill
            </button>
          </div>

          <div className="skills-table">
            {profile.skills.map((skill, index) => (
              <div key={`${skill.name}-${index}`} className="skill-row">
                <input
                  value={skill.name}
                  onChange={(event) => updateSkill(index, 'name', event.target.value)}
                  placeholder="Skill name"
                />
                <input
                  type="number"
                  value={skill.years}
                  onChange={(event) => updateSkill(index, 'years', event.target.value)}
                  placeholder="Years"
                />
                <input
                  type="number"
                  step="0.1"
                  value={skill.confidence}
                  onChange={(event) => updateSkill(index, 'confidence', event.target.value)}
                  placeholder="Confidence"
                />
                <input
                  value={skill.evidence}
                  onChange={(event) => updateSkill(index, 'evidence', event.target.value)}
                  placeholder="Evidence"
                />
                <button className="danger-button" type="button" onClick={() => removeSkill(index)}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        </section>
      </section>

      <aside className="page-side">
        <section className="panel">
          <p className="eyebrow">Upload samples</p>
          <h3>CV, motivation-letter, and reference material</h3>
          <label className="field">
            <span>Asset kind</span>
            <select value={assetKind} onChange={(event) => setAssetKind(event.target.value as ProfileAssetKind)}>
              <option value="cv">cv</option>
              <option value="motivation_letter">motivation_letter</option>
              <option value="reference_letter">reference_letter</option>
              <option value="previous_application">previous_application</option>
              <option value="other">other</option>
            </select>
          </label>
          <label className="upload-field">
            <input type="file" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="primary-button" type="button" onClick={handleUpload} disabled={uploading}>
            {uploading ? 'Uploading…' : 'Upload asset'}
          </button>
        </section>

        <section className="panel">
          <p className="eyebrow">Vault snapshot</p>
          <h3>Reuse signals</h3>
          <div className="compact-stats">
            <div>
              <strong>{vault?.assets.length ?? 0}</strong>
              <small>assets</small>
            </div>
            <div>
              <strong>{vault?.cv_style_samples.length ?? 0}</strong>
              <small>CV style samples</small>
            </div>
            <div>
              <strong>{vault?.motivation_letter_samples.length ?? 0}</strong>
              <small>letter samples</small>
            </div>
          </div>
          <p className="subtle-copy">Last updated {vault ? formatDate(vault.updated_at) : 'not yet available'}.</p>
        </section>

        <section className="panel">
          <p className="eyebrow">Uploaded assets</p>
          <div className="compact-list">
            {vault?.assets.map((asset) => (
              <div key={asset.asset_id} className="compact-asset">
                <span>{asset.file_name}</span>
                <small>
                  {asset.kind} · {formatDate(asset.imported_at)}
                </small>
                <p>{asset.extracted_text_excerpt}</p>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </div>
  )
}

function parseInlineList(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function parseLineList(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}
