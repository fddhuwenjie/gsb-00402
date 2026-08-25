import { Descriptions, Spin, Tag, Collapse, Table, Button, Empty, Tooltip, message } from 'antd'
import { ArrowLeftOutlined, DownloadOutlined, CopyOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { analysisApi } from '../api/client'

const statusMap = {
  pending: { color: 'default', text: '等待中' },
  running: { color: 'processing', text: '运行中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
}

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }
const matchTypeLabels = { exact: '精确匹配', prefix: '前缀匹配', substring: '子串匹配', fuzzy: '模糊匹配' }

export default function AnalysisDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      analysisApi.get(id).then((res) => setDetail(res.data)),
      analysisApi.getReport(id).then((res) => setReport(res.data)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [id])

  const handleDownload = () => {
    if (!report) return
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cbom-report-${id}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('报告已下载')
  }

  const handleCopyJSON = () => {
    if (!report) return
    navigator.clipboard.writeText(JSON.stringify(report, null, 2))
    message.success('JSON已复制到剪贴板')
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到分析任务</div>

  const task = detail.task
  const result = detail.result
  const status = statusMap[task.status] || { color: 'default', text: task.status }

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
    {
      title: '上下文', dataIndex: 'context', ellipsis: true,
      render: (v) => <code style={{ fontSize: 12 }}>{v}</code>,
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')}>返回</Button>
        <h2>分析详情</h2>
        {report && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <Button icon={<CopyOutlined />} onClick={handleCopyJSON}>复制JSON</Button>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownload}>下载报告</Button>
          </div>
        )}
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="任务信息">
          <Descriptions.Item label="任务名称">{task.name}</Descriptions.Item>
          <Descriptions.Item label="状态"><Tag color={status.color}>{status.text}</Tag></Descriptions.Item>
          <Descriptions.Item label="代码语言"><Tag color="blue">{task.language?.toUpperCase()}</Tag></Descriptions.Item>
          <Descriptions.Item label="项目标识">{task.project_key}</Descriptions.Item>
          <Descriptions.Item label="代码路径">{task.code_path}</Descriptions.Item>
          <Descriptions.Item label="特征文件">
            {task.signature_file_names?.map((n, i) => <Tag key={i}>{n}</Tag>)}
          </Descriptions.Item>
          <Descriptions.Item label="创建者">{task.creator_name}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(task.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
          {task.error_message && (
            <Descriptions.Item label="错误信息" span={2}>
              <span style={{ color: '#ff4d4f' }}>{task.error_message}</span>
            </Descriptions.Item>
          )}
        </Descriptions>
      </div>

      {result && (
        <div className="report-section">
          <Descriptions bordered column={3} title="分析结果摘要">
            <Descriptions.Item label="扫描文件数">{result.total_files_scanned}</Descriptions.Item>
            <Descriptions.Item label="匹配数">{result.total_matches}</Descriptions.Item>
            <Descriptions.Item label="组件数">{result.total_components}</Descriptions.Item>
            <Descriptions.Item label="风险等级">
              <Tag color={riskColors[result.risk_level]}>{riskLabels[result.risk_level] || result.risk_level}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="扫描耗时">{result.scan_duration?.toFixed(3)} 秒</Descriptions.Item>
          </Descriptions>
        </div>
      )}

      {report?.components?.length > 0 ? (
        <div className="report-section">
          <h3 style={{ marginBottom: 16 }}>密码组件详情</h3>
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
                        <Tooltip title="最高置信度">
                          <Tag color={func.best_confidence >= 0.9 ? 'green' : func.best_confidence >= 0.7 ? 'orange' : 'red'}>
                            {Math.round(func.best_confidence * 100)}%
                          </Tag>
                        </Tooltip>
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
        task.status === 'completed' && (
          <div className="report-section">
            <Empty description="未发现密码学组件" />
          </div>
        )
      )}
    </div>
  )
}
