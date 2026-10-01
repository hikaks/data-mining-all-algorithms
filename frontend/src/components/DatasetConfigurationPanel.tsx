import {useEffect, useState} from 'react';
import {jobPath, request} from '../api';
import {Panel, Notice, Loading, BarChart, DataTable, errorMessage, useResource} from './ui';
import type {DatasetConfiguration, DatasetSchema, FeatureKind, JobOverview} from '../types';

export default function DatasetConfigurationPanel({job, refresh}: {job: JobOverview; refresh: () => Promise<void>}) {
  const [sheet, setSheet] = useState(job.sheet_name ?? '');
  const [delimiter, setDelimiter] = useState<DatasetConfiguration['delimiter']>(null);
  const [target, setTarget] = useState('');
  const [profile, setProfile] = useState<DatasetConfiguration['profile']>('generic');
  const [features, setFeatures] = useState<DatasetConfiguration['features']>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const params = new URLSearchParams();
  if (sheet) params.set('sheet_name', sheet);
  if (delimiter) params.set('delimiter', delimiter);
  if (target) params.set('target_column', target);
  const schema = useResource<DatasetSchema>(`${jobPath(job.job_id, 'dataset/schema')}?${params}`);
  useEffect(() => {
    if (!job.configuration_ready) return;
    let active = true;
    request<DatasetConfiguration>(jobPath(job.job_id, 'dataset/configuration')).then(config => {
      if (!active) return;
      setProfile(config.profile); setSheet(config.sheet_name ?? ''); setDelimiter(config.delimiter); setTarget(config.target_column); setFeatures(config.features);
    }).catch(caught => {if (active) setError(errorMessage(caught));});
    return () => {active = false;};
  }, [job.job_id]);
  const locked = schema.data?.locked ?? !['UPLOADED', 'ANALYZED'].includes(job.status);
  function resetSource() {setTarget(''); setFeatures([]); setProfile('generic'); setSuccess(false);}
  async function save() {
    setBusy(true); setError(null); setSuccess(false);
    try {
      const payload = {profile, sheet_name: sheet || null, delimiter: delimiter || schema.data?.delimiter || null, target_column: profile === 'maxkomp' ? 'keputusan_laporan' : target, features: profile === 'maxkomp' ? [] : features};
      const config = await request<DatasetConfiguration>(jobPath(job.job_id, 'dataset/configuration'), {method: 'PUT', body: JSON.stringify(payload)});
      setTarget(config.target_column); setFeatures(config.features);
      await refresh(); setSuccess(true);
    } catch(caught) {setError(errorMessage(caught));} finally {setBusy(false);}
  }
  return <Panel title="Target & fitur dataset" note={locked ? 'KONFIGURASI TERKUNCI' : 'KONFIGURASI SEKALI PER JOB'}>
    <p className="muted-copy">Pilih kolom label yang sudah tersedia, bukan labeling manual. Konfigurasi dikunci setelah cleaning; perubahan berikutnya memerlukan job baru.</p>
    {error && <Notice tone="error">{error}</Notice>}
    {schema.error && <Notice tone="error">{schema.error}</Notice>}
    {success && <Notice tone="success">Konfigurasi tersimpan. Lanjutkan Data Understanding lalu cleaning.</Notice>}
    {!job.configuration_ready && <Notice>Preview raw tersedia. Tahap processing terkunci sampai konfigurasi valid disimpan.</Notice>}
    <div className="form-row config-controls">
      {job.file_format !== 'csv' ? <label>Sheet<select aria-label="Sheet dataset" value={sheet} disabled={locked || busy} onChange={e => {resetSource(); setSheet(e.target.value);}}>{(schema.data?.sheets ?? job.sheets).map(name => <option key={name}>{name}</option>)}</select></label> : <label>Pemisah CSV<select aria-label="Pemisah CSV" disabled={locked || busy} value={delimiter ?? ''} onChange={e => {resetSource(); setDelimiter((e.target.value || null) as DatasetConfiguration['delimiter']);}}><option value="">Deteksi otomatis</option><option value=",">Koma</option><option value=";">Titik koma</option><option value={'\t'}>Tab</option></select></label>}
      <label>Profil<select aria-label="Profil dataset" value={profile} disabled={locked || busy} onChange={e => {setProfile(e.target.value as DatasetConfiguration['profile']); setSuccess(false);}}><option value="generic">Umum — label dari kolom</option><option value="maxkomp" disabled={!schema.data?.maxkomp_available}>PT Maxkomp — kontrak resmi</option></select></label>
    </div>
    {schema.loading && <Loading/>}
    {schema.data && <>
      <h3>Preview sheet / pemisah terpilih</h3>
      <DataTable columns={schema.data.columns.map(column => column.name)} items={schema.data.preview}/>
      {schema.data.delimiter_ambiguous && <Notice>Deteksi pemisah ambigu. Periksa preview dan koreksi pemisah sebelum menyimpan.</Notice>}
      {profile === 'maxkomp' ? <Notice>Preset mempertahankan identifikasi otomatis, pemetaan domain, tujuh fitur resmi, dan periode penelitian PT Maxkomp. Target: keputusan_laporan.</Notice> : <>
        <label className="config-target">Kolom label / target<select aria-label="Kolom target" value={target} disabled={locked || busy} onChange={e => {setTarget(e.target.value); setFeatures(current => current.filter(feature => feature.name !== e.target.value)); setSuccess(false);}}><option value="">Pilih target</option>{schema.data.columns.map(column => <option key={column.name}>{column.name}</option>)}</select></label>
        <div className="table-scroll"><table className="data-table"><thead><tr><th>Gunakan</th><th>Fitur</th><th>Jenis</th><th>Kosong</th><th>Nilai unik</th></tr></thead><tbody>{schema.data.columns.map(column => {
          const selected = features.find(feature => feature.name === column.name);
          return <tr key={column.name}><td><input type="checkbox" aria-label={`Gunakan fitur ${column.name}`} checked={!!selected} disabled={locked || busy || column.name === target} onChange={e => {setFeatures(current => e.target.checked ? [...current, {name: column.name, kind: column.dtype}] : current.filter(feature => feature.name !== column.name)); setSuccess(false);}}/></td><td>{column.name}{column.name === target ? ' (target)' : ''}</td><td><select aria-label={`Jenis fitur ${column.name}`} value={selected?.kind ?? column.dtype} disabled={locked || busy || !selected} onChange={e => {setFeatures(current => current.map(feature => feature.name === column.name ? {...feature, kind: e.target.value as FeatureKind} : feature)); setSuccess(false);}}><option value="numeric">Numerik</option><option value="categorical">Kategori</option><option value="text">Teks</option><option value="date">Tanggal</option></select></td><td>{column.missing_count}</td><td>{column.unique_count}</td></tr>;
        })}</tbody></table></div>
        {target && <><h3>Distribusi target</h3><BarChart items={schema.data.target_distribution.map(item => ({label: item.value, value: item.count}))}/><p className="muted-copy">{schema.data.target_missing} target kosong akan dikecualikan dengan audit saat preprocessing. Target numerik diperlakukan sebagai kode kelas, bukan regresi.</p></>}
        {!!schema.data.warnings.length && <Notice>{schema.data.warnings.join(' ')}</Notice>}
      </>}
      {!locked && <button className="primary-button" disabled={busy || (profile === 'generic' && (!target || !features.length))} onClick={() => void save()}>{busy ? 'Menyimpan…' : 'Simpan konfigurasi'}</button>}
    </>}
  </Panel>;
}
