import { Descriptions, Spin, Tag, Table, Button, Collapse, Empty, message } from 'antd'
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }
const matchTypeLabels = { exact: '精确匹配', prefix: '前缀匹配', substring: '子串匹配', fuzzy: '模糊匹配' }

export default function BaselineDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    baselineApi.get(id).then((res) => setDetail(res.data)).finally(() => setLoading(false))
  }, [id])

  const handleDownload = () => {
    if (!detail?.report) return
    const blob = new Blob([JSON.stringify(detail.report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cbom-baseline-${id}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('基线报告已下载')
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到基线</div>

  const report = detail.report || {}
  const summary = report.summary || {}

  const locationColumns = [
    { title: '文件', dataIndex: 'file', ellipsis: true },
    { title: '行号', dataIndex: 'line', width: 70, align: 'center' },
    { title: '匹配文本', dataIndex: 'matched_text', width: 200 },
    {
      title: '置信度', dataIndex: 'confidence', width: 90, align: 'center',
      render: (v) => {
        const pct = Math.round(v * 100)
        const color = pct >= 90 ? 'green' : pct >= 70 ? 'orange' : 'red'
        return <Tag color={color}>{pct}%</Tag>
      },
    },
    { title: '上下文', dataIndex: 'context', ellipsis: true, render: (v) => <code style={{ fontSize: 12 }}>{v}</code> },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/baselines')}>返回</Button>
        <h2>基线详情</h2>
        <div style={{ marginLeft: 'auto' }}>
          <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownload}>下载基线JSON</Button>
        </div>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="基线信息">
          <Descriptions.Item label="基线名称">{detail.name}</Descriptions.Item>
          <Descriptions.Item label="语言"><Tag color="blue">{detail.language?.toUpperCase()}</Tag></Descriptions.Item>
          <Descriptions.Item label="项目标识"><code>{detail.project_key || '-'}</code></Descriptions.Item>
          <Descriptions.Item label="资产数" span={2}><Tag color="purple">{detail.asset_count}</Tag></Descriptions.Item>
          <Descriptions.Item label="代码路径" span={2}>{detail.code_path}</Descriptions.Item>
          <Descriptions.Item label="说明" span={2}>{detail.description || '（无）'}</Descriptions.Item>
          <Descriptions.Item label="创建者">{detail.creator_name}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="report-section">
        <Descriptions bordered column={3} title="快照摘要">
          <Descriptions.Item label="扫描文件数">{summary.total_files_scanned}</Descriptions.Item>
          <Descriptions.Item label="匹配数">{summary.total_matches}</Descriptions.Item>
          <Descriptions.Item label="组件数">{summary.total_crypto_components}</Descriptions.Item>
          <Descriptions.Item label="风险等级">
            <Tag color={riskColors[summary.risk_level]}>{riskLabels[summary.risk_level] || summary.risk_level}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="扫描耗时">{summary.scan_duration_seconds} 秒</Descriptions.Item>
        </Descriptions>
      </div>

      {report.components?.length > 0 ? (
        <div className="report-section">
          <h3 style={{ marginBottom: 16 }}>密码组件（快照）</h3>
          <Collapse
            items={report.components.map((comp, idx) => ({
              key: idx,
              label: (
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <strong>{comp.name}</strong>
                  <Tag>{comp.type}</Tag>
                  <Tag color="blue">{comp.total_function_matches} 函数</Tag>
                  <Tag color="cyan">{comp.total_occurrences} 次出现</Tag>
                  <Tag color="purple">{comp.files_involved} 文件</Tag>
                </div>
              ),
              children: (
                <div>
                  {comp.functions?.map((func, fIdx) => (
                    <div key={fIdx} className="component-card">
                      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
                        <code style={{ fontSize: 14, fontWeight: 600 }}>{func.signature}</code>
                        <Tag>{matchTypeLabels[func.match_type] || func.match_type}</Tag>
                        <Tag color={func.best_confidence >= 0.9 ? 'green' : func.best_confidence >= 0.7 ? 'orange' : 'red'}>
                          {Math.round(func.best_confidence * 100)}%
                        </Tag>
                      </div>
                      <Table
                        dataSource={func.locations}
                        columns={locationColumns}
                        rowKey={(r, i) => `${r.file}-${r.line}-${i}`}
                        size="small"
                        pagination={func.locations?.length > 10 ? { pageSize: 10 } : false}
                      />
                    </div>
                  ))}
                </div>
              ),
            }))}
          />
        </div>
      ) : (
        <div className="report-section">
          <Empty description="该基线未发现密码学组件" />
        </div>
      )}
    </div>
  )
}
