import { Descriptions, Spin, Tag, Table, Button, Empty, Tabs, Row, Col, Typography, Collapse } from 'antd'
import { ArrowLeftOutlined, ArrowUpOutlined, ArrowDownOutlined, SwapOutlined, MinusOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { diffApi } from '../api/client'

const { Text } = Typography

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }
const changedFieldLabels = {
  occurrences: '出现次数',
  lines: '行号位置',
  confidence: '置信度',
  match_type: '匹配类型',
  risk_level: '风险级别',
}

const assetColumns = [
  { title: '文件', dataIndex: 'file', ellipsis: true, width: 200 },
  {
    title: '语言', dataIndex: 'language', width: 80, align: 'center',
    render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
  },
  {
    title: '算法/库', dataIndex: 'algorithm_name', width: 130,
    render: (v, r) => <><Text strong>{v}</Text><br /><Text type="secondary" style={{ fontSize: 12 }}>{r.algorithm}</Text></>,
  },
  {
    title: '函数签名', dataIndex: 'signature', width: 200, ellipsis: true,
    render: (v) => <code style={{ fontSize: 12 }}>{v}</code>,
  },
  {
    title: '风险级别', dataIndex: 'risk_level', width: 90, align: 'center',
    render: (v) => <Tag color={riskColors[v] || 'default'}>{riskLabels[v] || v}</Tag>,
  },
  { title: '出现次数', dataIndex: 'occurrences', width: 90, align: 'center' },
  {
    title: '行号', dataIndex: 'lines', width: 140,
    render: (lines) => lines?.map((l) => <Tag key={l} style={{ marginBottom: 2 }}>{l}</Tag>),
  },
]

const changedColumns = [
  { title: '文件', dataIndex: ['current', 'file'], ellipsis: true, width: 180 },
  {
    title: '语言', dataIndex: ['current', 'language'], width: 80, align: 'center',
    render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
  },
  {
    title: '算法/库', dataIndex: ['current', 'algorithm_name'], width: 130,
    render: (v, r) => <><Text strong>{v}</Text><br /><Text type="secondary" style={{ fontSize: 12 }}>{r.current.algorithm}</Text></>,
  },
  {
    title: '函数签名', dataIndex: ['current', 'signature'], width: 190, ellipsis: true,
    render: (v) => <code style={{ fontSize: 12 }}>{v}</code>,
  },
  {
    title: '变化属性', dataIndex: 'changed_fields', width: 150,
    render: (fields) => fields.map((f) => (
      <Tag key={f} color="orange" style={{ marginBottom: 2 }}>{changedFieldLabels[f] || f}</Tag>
    )),
  },
  {
    title: '基线 → 当前', width: 220,
    render: (_, r) => (
      <div style={{ fontSize: 12 }}>
        {r.changed_fields.includes('occurrences') && (
          <div>出现次数：<Text delete>{r.baseline.occurrences}</Text> → <Text strong>{r.current.occurrences}</Text></div>
        )}
        {r.changed_fields.includes('confidence') && (
          <div>置信度：<Text delete>{Math.round(r.baseline.confidence * 100)}%</Text> → <Text strong>{Math.round(r.current.confidence * 100)}%</Text></div>
        )}
        {r.changed_fields.includes('risk_level') && (
          <div>
            风险：
            <Tag color={riskColors[r.baseline.risk_level]}>{riskLabels[r.baseline.risk_level]}</Tag>
            →
            <Tag color={riskColors[r.current.risk_level]}>{riskLabels[r.current.risk_level]}</Tag>
          </div>
        )}
        {r.changed_fields.includes('match_type') && (
          <div>匹配：<Text delete>{r.baseline.match_type}</Text> → <Text strong>{r.current.match_type}</Text></div>
        )}
        {r.changed_fields.includes('lines') && (
          <div>行号：<Text delete>{r.baseline.lines?.join(', ')}</Text> → <Text strong>{r.current.lines?.join(', ')}</Text></div>
        )}
      </div>
    ),
  },
]

function CategoryTable({ title, data, colorMap }) {
  const rows = Object.entries(data || {})
  if (rows.length === 0) return null
  const columns = [
    { title, dataIndex: 'name', ellipsis: true },
    {
      title: '新增', dataIndex: 'added', width: 80, align: 'center',
      render: (v) => <Tag color={v > 0 ? 'green' : 'default'}>{v}</Tag>,
    },
    {
      title: '移除', dataIndex: 'removed', width: 80, align: 'center',
      render: (v) => <Tag color={v > 0 ? 'red' : 'default'}>{v}</Tag>,
    },
    {
      title: '变化', dataIndex: 'changed', width: 80, align: 'center',
      render: (v) => <Tag color={v > 0 ? 'orange' : 'default'}>{v}</Tag>,
    },
    {
      title: '合计', dataIndex: 'total', width: 80, align: 'center',
      render: (v, row) => colorMap ? <Tag color={colorMap[row.name]}>{v}</Tag> : <Text strong>{v}</Text>,
    },
  ]
  return (
    <Table
      dataSource={rows.map(([name, b]) => ({ key: name, name, ...b }))}
      columns={columns}
      size="small"
      pagination={false}
    />
  )
}

export default function DiffDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    diffApi.get(id)
      .then((res) => setDetail(res.data))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到差异报告</div>

  const diff = detail.diff || {}
  const summary = diff.summary || {}
  const stats = [
    { label: '新增资产', value: summary.added ?? detail.added_count, icon: <ArrowUpOutlined />, color: '#52c41a' },
    { label: '移除资产', value: summary.removed ?? detail.removed_count, icon: <ArrowDownOutlined />, color: '#ff4d4f' },
    { label: '属性变化', value: summary.changed ?? detail.changed_count, icon: <SwapOutlined />, color: '#faad14' },
    { label: '未变化', value: summary.unchanged ?? 0, icon: <MinusOutlined />, color: '#8c8c8c' },
  ]

  const tabItems = [
    {
      key: 'added',
      label: <span>新增资产 <Tag color="green">{diff.added?.length || 0}</Tag></span>,
      children: diff.added?.length > 0 ? (
        <Table dataSource={diff.added} columns={assetColumns} rowKey="key" size="small" scroll={{ x: 1000 }}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 条` }} />
      ) : <Empty description="无新增密码资产" />,
    },
    {
      key: 'removed',
      label: <span>移除资产 <Tag color="red">{diff.removed?.length || 0}</Tag></span>,
      children: diff.removed?.length > 0 ? (
        <Table dataSource={diff.removed} columns={assetColumns} rowKey="key" size="small" scroll={{ x: 1000 }}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 条` }} />
      ) : <Empty description="无移除密码资产" />,
    },
    {
      key: 'changed',
      label: <span>属性变化 <Tag color="orange">{diff.changed?.length || 0}</Tag></span>,
      children: diff.changed?.length > 0 ? (
        <Table dataSource={diff.changed} columns={changedColumns} rowKey="key" size="small" scroll={{ x: 1050 }}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 条` }} />
      ) : <Empty description="无属性变化的密码资产" />,
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/diffs')}>返回</Button>
        <h2>差异报告详情</h2>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="报告信息">
          <Descriptions.Item label="报告名称" span={2}>{detail.name}</Descriptions.Item>
          <Descriptions.Item label="基线">
            <a onClick={() => navigate(`/baselines/${detail.baseline_id}`)}>{diff.baseline?.name || detail.baseline_name}</a>
            <span style={{ color: '#999', marginLeft: 8 }}>
              {diff.baseline?.task_name || ''}（{diff.baseline?.language?.toUpperCase()}）
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="当前分析">
            <a onClick={() => navigate(`/analyses/${detail.task_id}`)}>{diff.current?.task_name || detail.task_name}</a>
            <span style={{ color: '#999', marginLeft: 8 }}>
              #{detail.task_id}（{diff.current?.language?.toUpperCase()}）
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="资产数 基线 → 当前">
            {summary.baseline_asset_count ?? '-'} → {summary.current_asset_count ?? '-'}
          </Descriptions.Item>
          <Descriptions.Item label="差异风险级别">
            <Tag color={riskColors[detail.risk_level]}>{riskLabels[detail.risk_level] || detail.risk_level}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建者">{detail.creator_name}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
        </Descriptions>
      </div>

      <Row gutter={[16, 16]}>
        {stats.map((s, i) => (
          <Col xs={12} md={6} key={i}>
            <div className="stat-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div className="stat-number" style={{ color: s.color }}>{s.value}</div>
                  <div className="stat-label">{s.label}</div>
                </div>
                <div style={{ fontSize: 32, color: s.color, opacity: 0.25 }}>{s.icon}</div>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      <div className="report-section" style={{ marginTop: 16 }}>
        <h3 style={{ marginBottom: 16 }}>差异分类汇总</h3>
        <Collapse
          defaultActiveKey={['file']}
          items={[
            {
              key: 'file',
              label: <strong>按文件分类</strong>,
              children: <CategoryTable title="文件" data={diff.categories?.by_file} />,
            },
            {
              key: 'language',
              label: <strong>按语言分类</strong>,
              children: <CategoryTable title="语言" data={diff.categories?.by_language} />,
            },
            {
              key: 'algorithm',
              label: <strong>按算法/库分类</strong>,
              children: <CategoryTable title="算法/库" data={diff.categories?.by_algorithm} />,
            },
            {
              key: 'risk',
              label: <strong>按风险级别分类</strong>,
              children: <CategoryTable
                title="风险级别"
                data={Object.fromEntries(
                  Object.entries(diff.categories?.by_risk_level || {}).map(
                    ([k, v]) => [riskLabels[k] || k, v]
                  )
                )}
                colorMap={Object.fromEntries(
                  Object.entries(riskLabels).map(([k, label]) => [label, riskColors[k]])
                )}
              />,
            },
          ]}
        />
      </div>

      <div className="report-section">
        <Tabs defaultActiveKey="added" items={tabItems} />
      </div>
    </div>
  )
}
