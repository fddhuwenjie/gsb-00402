import { Descriptions, Spin, Tag, Table, Button, Empty, Tabs, Card, Row, Col, Statistic } from 'antd'
import { ArrowLeftOutlined, PlusCircleOutlined, MinusCircleOutlined, SwapOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

const changeTypeTag = (type) => {
  if (type === 'added') return <Tag color="green">新增</Tag>
  if (type === 'removed') return <Tag color="red">移除</Tag>
  return <Tag color="orange">变化</Tag>
}

function GroupTable({ data }) {
  const rows = Object.entries(data || {}).map(([name, v]) => ({ name, ...v }))
  const columns = [
    { title: '分类', dataIndex: 'name', ellipsis: true },
    { title: '新增', dataIndex: 'added', width: 80, align: 'center', render: (v) => <Tag color="green">+{v}</Tag> },
    { title: '移除', dataIndex: 'removed', width: 80, align: 'center', render: (v) => <Tag color="red">-{v}</Tag> },
    { title: '变化', dataIndex: 'changed', width: 80, align: 'center', render: (v) => <Tag color="orange">~{v}</Tag> },
    { title: '合计', dataIndex: 'total', width: 80, align: 'center' },
  ]
  return <Table dataSource={rows} columns={columns} rowKey="name" size="small" pagination={rows.length > 10 ? { pageSize: 10 } : false} />
}

export default function DiffDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    baselineApi.getDiff(id)
      .then((res) => setDetail(res.data))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到差异报告</div>

  const { report, diff } = detail
  const summary = diff.summary || {}
  const grouped = diff.grouped || {}

  const assetColumns = (changeType) => [
    { title: '类型', width: 70, align: 'center', render: () => changeTypeTag(changeType) },
    { title: '算法 / 组件', dataIndex: 'algorithm', width: 150 },
    { title: '函数签名', dataIndex: 'signature', width: 220, render: (v) => <code>{v}</code> },
    { title: '语言', dataIndex: 'language', width: 80, align: 'center', render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag> },
    {
      title: '风险级别', dataIndex: 'risk_level', width: 90, align: 'center',
      render: (v) => <Tag color={riskColors[v]}>{riskLabels[v] || v}</Tag>,
    },
    { title: '出现次数', dataIndex: 'occurrences', width: 90, align: 'center' },
    {
      title: '涉及文件', dataIndex: 'files', ellipsis: true,
      render: (files) => files?.map((f, i) => <Tag key={i} style={{ marginBottom: 2 }}>{f}</Tag>),
    },
  ]

  const changedColumns = [
    { title: '类型', width: 70, align: 'center', render: () => changeTypeTag('changed') },
    { title: '算法 / 组件', dataIndex: 'algorithm', width: 150 },
    { title: '函数签名', dataIndex: 'signature', width: 200, render: (v) => <code>{v}</code> },
    { title: '语言', dataIndex: 'language', width: 80, align: 'center', render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag> },
    {
      title: '风险级别', dataIndex: 'risk_level', width: 90, align: 'center',
      render: (v) => <Tag color={riskColors[v]}>{riskLabels[v] || v}</Tag>,
    },
    {
      title: '属性变化', dataIndex: 'changes', ellipsis: true,
      render: (changes) => Object.entries(changes || {}).map(([attr, c]) => (
        <div key={attr} style={{ fontSize: 12 }}>
          <code>{attr}</code>: <span style={{ color: '#ff4d4f' }}>{JSON.stringify(c.before)}</span>
          {' → '}<span style={{ color: '#52c41a' }}>{JSON.stringify(c.after)}</span>
        </div>
      )),
    },
  ]

  const makeTable = (rows, columns) => (
    <Table
      dataSource={rows}
      columns={columns}
      rowKey={(r) => r.key}
      size="small"
      pagination={rows?.length > 10 ? { pageSize: 10 } : false}
      locale={{ emptyText: <Empty description="无记录" /> }}
    />
  )

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/baselines/${report.baseline_id}`)}>返回</Button>
        <h2>差异报告详情</h2>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="报告信息">
          <Descriptions.Item label="基线">
            <a onClick={() => navigate(`/baselines/${report.baseline_id}`)}>{report.baseline_name}</a>
          </Descriptions.Item>
          <Descriptions.Item label="对比分析">
            <a onClick={() => navigate(`/analyses/${report.task_id}`)}>#{report.task_id} {report.task_name}</a>
          </Descriptions.Item>
          <Descriptions.Item label="创建者">{report.creator_name}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(report.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="report-section">
        <Row gutter={16}>
          <Col span={6}><Card><Statistic title="新增资产" value={summary.added || 0} prefix={<PlusCircleOutlined />} valueStyle={{ color: '#52c41a' }} /></Card></Col>
          <Col span={6}><Card><Statistic title="移除资产" value={summary.removed || 0} prefix={<MinusCircleOutlined />} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
          <Col span={6}><Card><Statistic title="属性变化" value={summary.changed || 0} prefix={<SwapOutlined />} valueStyle={{ color: '#fa8c16' }} /></Card></Col>
          <Col span={6}><Card><Statistic title="未变化" value={summary.unchanged || 0} /></Card></Col>
        </Row>
      </div>

      {summary.total_changes === 0 ? (
        <div className="report-section"><Empty description="与基线相比无差异" /></div>
      ) : (
        <>
          <div className="report-section">
            <h3 style={{ marginBottom: 16 }}>差异分类统计</h3>
            <Tabs
              items={[
                { key: 'file', label: '按文件', children: <GroupTable data={grouped.by_file} /> },
                { key: 'language', label: '按语言', children: <GroupTable data={grouped.by_language} /> },
                { key: 'algorithm', label: '按算法名称', children: <GroupTable data={grouped.by_algorithm} /> },
                { key: 'risk', label: '按风险级别', children: <GroupTable data={grouped.by_risk} /> },
              ]}
            />
          </div>

          <div className="report-section">
            <h3 style={{ marginBottom: 16 }}>差异明细</h3>
            <Tabs
              items={[
                { key: 'added', label: `新增 (${summary.added || 0})`, children: makeTable(diff.added, assetColumns('added')) },
                { key: 'removed', label: `移除 (${summary.removed || 0})`, children: makeTable(diff.removed, assetColumns('removed')) },
                { key: 'changed', label: `变化 (${summary.changed || 0})`, children: makeTable(diff.changed, changedColumns) },
              ]}
            />
          </div>
        </>
      )}
    </div>
  )
}
