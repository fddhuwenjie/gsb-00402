import {
  Descriptions, Spin, Tag, Button, Table, Empty, Modal, Form, Select, Tabs,
  Statistic, Row, Col, message,
} from 'antd'
import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi, analysisApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }
const kindColors = { added: 'green', removed: 'red', changed: 'orange' }

export default function BaselineDetailPage() {
  const { id, diffId } = useParams()
  const navigate = useNavigate()
  const [baseline, setBaseline] = useState(null)
  const [diffs, setDiffs] = useState([])
  const [activeDiff, setActiveDiff] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [candidateTasks, setCandidateTasks] = useState([])
  const [generating, setGenerating] = useState(false)
  const [form] = Form.useForm()

  const loadBaseline = async () => {
    const [bRes, dRes] = await Promise.all([
      baselineApi.get(id),
      baselineApi.listDiffs(id),
    ])
    setBaseline(bRes.data)
    setDiffs(dRes.data)
    return dRes.data
  }

  useEffect(() => {
    setLoading(true)
    loadBaseline()
      .then((diffList) => {
        const target = diffId || diffList[0]?.id
        if (target) return baselineApi.getDiff(target).then((res) => setActiveDiff(res.data))
      })
      .finally(() => setLoading(false))
  }, [id, diffId])

  const openModal = async () => {
    setModalOpen(true)
    const res = await analysisApi.list(1, 100)
    // 一致性：仅允许项目标识和语言均与基线一致的已完成任务
    const candidates = res.data.items.filter(
      (t) => t.status === 'completed' && t.project_key === baseline.project_key && t.language === baseline.language
    )
    setCandidateTasks(candidates)
  }

  const handleGenerate = async () => {
    const values = await form.validateFields()
    setGenerating(true)
    try {
      const res = await baselineApi.generateDiff(id, values)
      message.success('差异报告已生成')
      setModalOpen(false)
      form.resetFields()
      await loadBaseline()
      setActiveDiff(res.data)
      navigate(`/baselines/${id}/diffs/${res.data.id}`)
    } finally {
      setGenerating(false)
    }
  }

  const selectDiff = async (diffRowId) => {
    const res = await baselineApi.getDiff(diffRowId)
    setActiveDiff(res.data)
    navigate(`/baselines/${id}/diffs/${diffRowId}`)
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!baseline) return <div style={{ textAlign: 'center', padding: 80 }}>未找到基线</div>

  const assetColumns = [
    { title: '算法/组件', dataIndex: 'algorithm', width: 140, ellipsis: true, render: (v) => <Tag color="geekblue">{v}</Tag> },
    { title: '函数签名', dataIndex: 'signature', ellipsis: true, render: (v) => <code style={{ fontSize: 12 }}>{v}</code> },
    { title: '语言', dataIndex: 'language', width: 80, align: 'center', render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag> },
    {
      title: '风险', dataIndex: 'risk_level', width: 90, align: 'center',
      render: (v) => <Tag color={riskColors[v]}>{riskLabels[v] || v}</Tag>,
    },
    { title: '出现次数', dataIndex: 'total_occurrences', width: 90, align: 'center' },
    { title: '涉及文件', dataIndex: 'files_involved', width: 90, align: 'center' },
  ]

  const fmtVal = (v) => (Array.isArray(v) ? (v.length ? v.join(', ') : '—') : String(v))

  const changedColumns = [
    ...assetColumns.slice(0, 4),
    {
      title: '变化', dataIndex: 'changes', width: 280,
      render: (changes) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {changes?.map((c, i) => (
            <span key={i} style={{ fontSize: 12 }}>
              <Tag>{c.field}</Tag>{fmtVal(c.from)} → <strong>{fmtVal(c.to)}</strong>
            </span>
          ))}
        </div>
      ),
    },
    {
      title: '文件变化', width: 220,
      render: (_, r) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 12 }}>
          {r.removed_files?.map((f, i) => <span key={`r${i}`}><Tag color="red">原</Tag>{f}</span>)}
          {r.added_files?.map((f, i) => <span key={`a${i}`}><Tag color="green">新</Tag>{f}</span>)}
          {!r.removed_files?.length && !r.added_files?.length && <span style={{ color: '#aaa' }}>—</span>}
        </div>
      ),
    },
  ]

  const renderCategory = (obj, title) => {
    const rows = Object.entries(obj || {}).map(([k, v]) => ({ key: k, name: k, ...v }))
    if (!rows.length) return <Empty description={`无${title}分类数据`} />
    return (
      <Table
        size="small"
        dataSource={rows}
        rowKey="key"
        pagination={rows.length > 10 ? { pageSize: 10 } : false}
        columns={[
          { title, dataIndex: 'name', ellipsis: true },
          { title: '新增', dataIndex: 'added', width: 90, align: 'center', render: (v) => <Tag color="green">{v || 0}</Tag> },
          { title: '移除', dataIndex: 'removed', width: 90, align: 'center', render: (v) => <Tag color="red">{v || 0}</Tag> },
          { title: '变化', dataIndex: 'changed', width: 90, align: 'center', render: (v) => <Tag color="orange">{v || 0}</Tag> },
        ]}
      />
    )
  }

  const diff = activeDiff?.diff
  const summary = diff?.summary

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/baselines')}>返回</Button>
        <h2>基线详情</h2>
        <div style={{ marginLeft: 'auto' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>生成差异报告</Button>
        </div>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="基线信息">
          <Descriptions.Item label="基线名称">{baseline.name}</Descriptions.Item>
          <Descriptions.Item label="语言"><Tag color="blue">{baseline.language?.toUpperCase()}</Tag></Descriptions.Item>
          <Descriptions.Item label="基线任务">{baseline.task_name} (#{baseline.task_id})</Descriptions.Item>
          <Descriptions.Item label="项目标识">{baseline.project_key}</Descriptions.Item>
          <Descriptions.Item label="代码路径">{baseline.code_path}</Descriptions.Item>
          <Descriptions.Item label="创建者">{baseline.creator_name}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(baseline.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
          {baseline.description && (
            <Descriptions.Item label="描述" span={2}>{baseline.description}</Descriptions.Item>
          )}
        </Descriptions>
      </div>

      <div className="report-section">
        <h3 style={{ marginBottom: 16 }}>差异报告</h3>
        {diffs.length === 0 ? (
          <Empty description="暂无差异报告，点击右上角“生成差异报告”" />
        ) : (
          <Table
            size="small"
            dataSource={diffs}
            rowKey="id"
            pagination={false}
            onRow={(record) => ({ onClick: () => selectDiff(record.id), style: { cursor: 'pointer' } })}
            rowClassName={(record) => (activeDiff?.id === record.id ? 'ant-table-row-selected' : '')}
            columns={[
              { title: 'ID', dataIndex: 'id', width: 55 },
              { title: '对比任务', dataIndex: 'task_name', ellipsis: true, render: (v, r) => `${v} (#${r.task_id})` },
              { title: '新增', dataIndex: 'total_added', width: 80, align: 'center', render: (v) => <Tag color="green">{v}</Tag> },
              { title: '移除', dataIndex: 'total_removed', width: 80, align: 'center', render: (v) => <Tag color="red">{v}</Tag> },
              { title: '变化', dataIndex: 'total_changed', width: 80, align: 'center', render: (v) => <Tag color="orange">{v}</Tag> },
              { title: '生成时间', dataIndex: 'created_at', width: 180, render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
            ]}
          />
        )}
      </div>

      {diff && (
        <div className="report-section">
          <h3 style={{ marginBottom: 16 }}>
            差异详情：{activeDiff.task_name} (#{activeDiff.task_id})
          </h3>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={8}><Statistic title="新增资产" value={summary?.total_added} valueStyle={{ color: '#52c41a' }} /></Col>
            <Col span={8}><Statistic title="移除资产" value={summary?.total_removed} valueStyle={{ color: '#ff4d4f' }} /></Col>
            <Col span={8}><Statistic title="属性变化" value={summary?.total_changed} valueStyle={{ color: '#fa8c16' }} /></Col>
          </Row>

          {summary?.total_added === 0 && summary?.total_removed === 0 && summary?.total_changed === 0 ? (
            <Empty description="基线与该分析之间无密码资产差异" />
          ) : (
            <Tabs
              items={[
                {
                  key: 'added', label: <span>新增 <Tag color={kindColors.added}>{summary?.total_added}</Tag></span>,
                  children: <Table size="small" dataSource={diff.added} columns={assetColumns} rowKey="key" pagination={{ pageSize: 10 }} locale={{ emptyText: '无新增资产' }} />,
                },
                {
                  key: 'removed', label: <span>移除 <Tag color={kindColors.removed}>{summary?.total_removed}</Tag></span>,
                  children: <Table size="small" dataSource={diff.removed} columns={assetColumns} rowKey="key" pagination={{ pageSize: 10 }} locale={{ emptyText: '无移除资产' }} />,
                },
                {
                  key: 'changed', label: <span>属性变化 <Tag color={kindColors.changed}>{summary?.total_changed}</Tag></span>,
                  children: <Table size="small" dataSource={diff.changed} columns={changedColumns} rowKey="key" pagination={{ pageSize: 10 }} locale={{ emptyText: '无属性变化' }} />,
                },
                { key: 'by_file', label: '按文件', children: renderCategory(diff.by_file, '文件') },
                { key: 'by_language', label: '按语言', children: renderCategory(diff.by_language, '语言') },
                { key: 'by_algorithm', label: '按算法', children: renderCategory(diff.by_algorithm, '算法') },
                { key: 'by_risk_level', label: '按风险级别', children: renderCategory(diff.by_risk_level, '风险级别') },
              ]}
            />
          )}
        </div>
      )}

      <Modal
        title="生成差异报告"
        open={modalOpen}
        onOk={handleGenerate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={generating}
        okText="生成"
        cancelText="取消"
      >
        <p style={{ color: '#888', fontSize: 13 }}>
          仅可选择项目标识和语言均与基线一致的已完成分析任务。
        </p>
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="task_id" label="对比分析任务" rules={[{ required: true, message: '请选择分析任务' }]}>
            <Select
              placeholder={candidateTasks.length ? '选择一致的已完成分析任务' : '无可对比的一致任务'}
              options={candidateTasks.map((t) => ({ value: t.id, label: `#${t.id} ${t.name}` }))}
              showSearch
              optionFilterProp="label"
              notFoundContent="无与基线一致的候选任务"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
