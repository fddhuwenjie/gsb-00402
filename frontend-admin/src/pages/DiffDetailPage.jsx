import { Descriptions, Spin, Tag, Table, Button, Empty, Tabs, Card, Statistic, Row, Col, Collapse, Tooltip, message } from 'antd'
import { ArrowLeftOutlined, DownloadOutlined, ArrowUpOutlined, ArrowDownOutlined, EditOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { diffApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

const changeLabels = {
  match_type: '匹配类型',
  confidence: '置信度',
  occurrences: '出现次数',
  risk_level: '风险等级',
  lines: '行号',
}

function assetColumns() {
  return [
    { title: '算法/库', dataIndex: 'algorithm_name', width: 140, ellipsis: true, render: (v) => <strong>{v}</strong> },
    { title: '函数签名', dataIndex: 'signature', ellipsis: true, render: (v) => <code style={{ fontSize: 12 }}>{v}</code> },
    { title: '文件', dataIndex: 'file', ellipsis: true },
    {
      title: '语言', dataIndex: 'language', width: 80, align: 'center',
      render: (v) => <Tag>{v?.toUpperCase()}</Tag>,
    },
    {
      title: '风险', dataIndex: 'risk_level', width: 80, align: 'center',
      render: (v) => <Tag color={riskColors[v]}>{riskLabels[v] || v}</Tag>,
    },
    { title: '匹配类型', dataIndex: 'match_type', width: 100, align: 'center' },
    {
      title: '置信度', dataIndex: 'confidence', width: 80, align: 'center',
      render: (v) => `${Math.round((v || 0) * 100)}%`,
    },
    { title: '出现', dataIndex: 'occurrences', width: 60, align: 'center' },
    {
      title: '行号', dataIndex: 'lines', width: 120, ellipsis: true,
      render: (lines) => lines?.map((l) => <Tag key={l} style={{ marginBottom: 2 }}>{l}</Tag>),
    },
  ]
}

function changedColumns() {
  return [
    { title: '算法/库', key: 'algorithm_name', width: 140, ellipsis: true, render: (_, r) => <strong>{r.after.algorithm_name}</strong> },
    { title: '函数签名', key: 'signature', ellipsis: true, render: (_, r) => <code style={{ fontSize: 12 }}>{r.after.signature}</code> },
    { title: '文件', key: 'file', ellipsis: true, render: (_, r) => r.after.file },
    {
      title: '语言', key: 'language', width: 80, align: 'center',
      render: (_, r) => <Tag>{r.after.language?.toUpperCase()}</Tag>,
    },
    {
      title: '变化字段', key: 'changed_fields', width: 160,
      render: (_, r) => r.changed_fields.map((f) => (
        <Tag key={f} color="orange">{changeLabels[f] || f}</Tag>
      )),
    },
    {
      title: '基线 → 当前', key: 'diff', width: 220,
      render: (_, r) => {
        const items = []
        for (const f of r.changed_fields) {
          if (f === 'lines') {
            items.push(<div key={f} style={{ fontSize: 12 }}>{changeLabels[f]}: {r.before.lines?.length || 0} → {r.after.lines?.length || 0} 处</div>)
          } else {
            items.push(<div key={f} style={{ fontSize: 12 }}>{changeLabels[f] || f}: <span style={{ color: '#999' }}>{String(r.before[f])}</span> → <strong>{String(r.after[f])}</strong></div>)
          }
        }
        return items
      },
    },
    {
      title: '风险', key: 'risk', width: 80, align: 'center',
      render: (_, r) => <Tag color={riskColors[r.after.risk_level]}>{riskLabels[r.after.risk_level] || r.after.risk_level}</Tag>,
    },
  ]
}

function ClassificationGroup({ groups, type }) {
  const entries = Object.entries(groups || {})
  if (entries.length === 0) return <Empty description="无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />

  const items = entries.map(([key, bucket]) => {
    const total = bucket.added.length + bucket.removed.length + bucket.changed.length
    if (total === 0) return null
    return {
      key,
      label: (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <strong>{key}</strong>
          {bucket.added.length > 0 && <Tag color="green">+{bucket.added.length}</Tag>}
          {bucket.removed.length > 0 && <Tag color="red">-{bucket.removed.length}</Tag>}
          {bucket.changed.length > 0 && <Tag color="orange">~{bucket.changed.length}</Tag>}
          <Tag>{total}</Tag>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {bucket.added.length > 0 && (
            <div>
              <div style={{ marginBottom: 6, color: '#52c41a', fontWeight: 600 }}>新增 ({bucket.added.length})</div>
              <Table size="small" rowKey={(r) => r.key} dataSource={bucket.added} columns={assetColumns()} pagination={false} scroll={{ x: 800 }} />
            </div>
          )}
          {bucket.removed.length > 0 && (
            <div>
              <div style={{ marginBottom: 6, color: '#ff4d4f', fontWeight: 600 }}>移除 ({bucket.removed.length})</div>
              <Table size="small" rowKey={(r) => r.key} dataSource={bucket.removed} columns={assetColumns()} pagination={false} scroll={{ x: 800 }} />
            </div>
          )}
          {bucket.changed.length > 0 && (
            <div>
              <div style={{ marginBottom: 6, color: '#fa8c16', fontWeight: 600 }}>属性变化 ({bucket.changed.length})</div>
              <Table size="small" rowKey={(r) => r.after.key} dataSource={bucket.changed} columns={changedColumns()} pagination={false} scroll={{ x: 800 }} />
            </div>
          )}
        </div>
      ),
    }
  }).filter(Boolean)

  return <Collapse items={items} defaultActiveKey={entries.length > 0 ? [entries[0][0]] : []} />
}

export default function DiffDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    diffApi.get(id).then((res) => setDetail(res.data)).finally(() => setLoading(false))
  }, [id])

  const handleDownload = () => {
    if (!detail?.diff) return
    const blob = new Blob([JSON.stringify(detail.diff, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cbom-diff-${id}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('差异报告已下载')
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到差异报告</div>

  const diff = detail.diff || {}
  const summary = diff.summary || {}
  const classified = diff.classified || {}

  const tabItems = [
    {
      key: 'overview',
      label: '总览',
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card>
            <Row gutter={16}>
              <Col span={4}><Statistic title="基线资产" value={summary.total_baseline_assets} /></Col>
              <Col span={4}><Statistic title="当前资产" value={summary.total_current_assets} /></Col>
              <Col span={4}>
                <Statistic title="新增" value={summary.added} valueStyle={{ color: '#52c41a' }} prefix={<ArrowUpOutlined />} />
              </Col>
              <Col span={4}>
                <Statistic title="移除" value={summary.removed} valueStyle={{ color: '#ff4d4f' }} prefix={<ArrowDownOutlined />} />
              </Col>
              <Col span={4}>
                <Statistic title="属性变化" value={summary.changed} valueStyle={{ color: '#fa8c16' }} prefix={<EditOutlined />} />
              </Col>
              <Col span={4}>
                <Statistic title="未变化" value={summary.unchanged} />
              </Col>
            </Row>
          </Card>
          {summary.added > 0 && (
            <Card title={<span><Tag color="green">新增</Tag>新增密码资产 ({summary.added})</span>}>
              <Table size="small" rowKey={(r) => r.key} dataSource={diff.added} columns={assetColumns()} pagination={{ pageSize: 10 }} scroll={{ x: 900 }} />
            </Card>
          )}
          {summary.removed > 0 && (
            <Card title={<span><Tag color="red">移除</Tag>移除密码资产 ({summary.removed})</span>}>
              <Table size="small" rowKey={(r) => r.key} dataSource={diff.removed} columns={assetColumns()} pagination={{ pageSize: 10 }} scroll={{ x: 900 }} />
            </Card>
          )}
          {summary.changed > 0 && (
            <Card title={<span><Tag color="orange">变化</Tag>属性变化资产 ({summary.changed})</span>}>
              <Table size="small" rowKey={(r) => r.after.key} dataSource={diff.changed} columns={changedColumns()} pagination={{ pageSize: 10 }} scroll={{ x: 900 }} />
            </Card>
          )}
          {summary.added === 0 && summary.removed === 0 && summary.changed === 0 && (
            <Empty description="与基线相比，密码资产无变化" />
          )}
        </div>
      ),
    },
    { key: 'by_file', label: '按文件分类', children: <ClassificationGroup groups={classified.by_file} type="file" /> },
    { key: 'by_language', label: '按语言分类', children: <ClassificationGroup groups={classified.by_language} type="language" /> },
    { key: 'by_algorithm', label: '按算法名称分类', children: <ClassificationGroup groups={classified.by_algorithm} type="algorithm" /> },
    { key: 'by_risk', label: '按风险级别分类', children: <ClassificationGroup groups={classified.by_risk} type="risk" /> },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
        <h2>差异报告详情</h2>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <Tag color={riskColors[detail.risk_level]} style={{ fontSize: 14, padding: '4px 12px' }}>
            差异风险：{riskLabels[detail.risk_level] || detail.risk_level}
          </Tag>
          <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownload}>下载JSON</Button>
        </div>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="差异元信息">
          <Descriptions.Item label="差异 ID">{detail.id}</Descriptions.Item>
          <Descriptions.Item label="生成时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
          <Descriptions.Item label="基线">{detail.baseline_name} (ID: {detail.baseline_id})</Descriptions.Item>
          <Descriptions.Item label="对比任务">{detail.task_name} (ID: {detail.task_id})</Descriptions.Item>
          <Descriptions.Item label="创建者">{detail.creator_name}</Descriptions.Item>
          <Descriptions.Item label="风险等级">
            <Tag color={riskColors[detail.risk_level]}>{riskLabels[detail.risk_level] || detail.risk_level}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </div>

      <div className="report-section">
        <Tabs defaultActiveKey="overview" items={tabItems} />
      </div>
    </div>
  )
}
