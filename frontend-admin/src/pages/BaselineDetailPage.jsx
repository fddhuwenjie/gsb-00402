import { Descriptions, Spin, Tag, Table, Button, Modal, Select, message, Collapse, Empty } from 'antd'
import { ArrowLeftOutlined, DiffOutlined, EyeOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi, analysisApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

export default function BaselineDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [diffs, setDiffs] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [completedTasks, setCompletedTasks] = useState([])
  const [selectedTask, setSelectedTask] = useState(null)
  const [generating, setGenerating] = useState(false)

  const fetchDiffs = () => baselineApi.listDiffs(id).then((res) => setDiffs(res.data || [])).catch(() => {})

  useEffect(() => {
    Promise.all([
      baselineApi.get(id).then((res) => setDetail(res.data)),
      fetchDiffs(),
    ]).finally(() => setLoading(false))
  }, [id])

  const openDiffModal = async () => {
    setModalOpen(true)
    const res = await analysisApi.list(1, 100)
    // 仅展示代码路径和语言均与基线一致的已完成分析任务
    setCompletedTasks((res.data.items || []).filter((t) =>
      t.status === 'completed'
      && t.code_path === baseline.code_path
      && t.language === baseline.language
    ))
  }

  const handleGenerate = async () => {
    if (!selectedTask) {
      message.warning('请选择要对比的分析任务')
      return
    }
    setGenerating(true)
    try {
      const res = await baselineApi.generateDiff(id, selectedTask)
      message.success('差异报告已生成')
      setModalOpen(false)
      navigate(`/diffs/${res.data.report.id}`)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到基线</div>

  const baseline = detail.baseline
  const assets = detail.assets || []

  const assetColumns = [
    { title: '算法 / 组件', dataIndex: 'algorithm', width: 150 },
    { title: '函数签名', dataIndex: 'signature', width: 220, render: (v) => <code>{v}</code> },
    { title: '类型', dataIndex: 'type', width: 130, render: (v) => <Tag>{v}</Tag> },
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

  const diffColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '对比分析', dataIndex: 'task_name', width: 200, ellipsis: true },
    { title: '新增', dataIndex: 'added_count', width: 80, align: 'center', render: (v) => <Tag color="green">+{v}</Tag> },
    { title: '移除', dataIndex: 'removed_count', width: 80, align: 'center', render: (v) => <Tag color="red">-{v}</Tag> },
    { title: '变化', dataIndex: 'changed_count', width: 80, align: 'center', render: (v) => <Tag color="orange">~{v}</Tag> },
    { title: '创建者', dataIndex: 'creator_name', width: 90 },
    {
      title: '创建时间', dataIndex: 'created_at', width: 180,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 80, align: 'center',
      render: (_, record) => (
        <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/diffs/${record.id}`)} />
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/baselines')}>返回</Button>
        <h2>基线详情</h2>
        <div style={{ marginLeft: 'auto' }}>
          <Button type="primary" icon={<DiffOutlined />} onClick={openDiffModal}>生成差异报告</Button>
        </div>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="基线信息">
          <Descriptions.Item label="基线名称">{baseline.name}</Descriptions.Item>
          <Descriptions.Item label="来源分析">
            <a onClick={() => navigate(`/analyses/${baseline.task_id}`)}>#{baseline.task_id} {baseline.task_name}</a>
          </Descriptions.Item>
          <Descriptions.Item label="代码语言"><Tag color="blue">{baseline.language?.toUpperCase()}</Tag></Descriptions.Item>
          <Descriptions.Item label="代码路径">{baseline.code_path}</Descriptions.Item>
          <Descriptions.Item label="资产数">{baseline.asset_count}</Descriptions.Item>
          <Descriptions.Item label="创建者">{baseline.creator_name}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(baseline.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="report-section">
        <h3 style={{ marginBottom: 16 }}>差异报告</h3>
        <Table
          dataSource={diffs}
          columns={diffColumns}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{ emptyText: <Empty description="尚未生成差异报告" /> }}
        />
      </div>

      <div className="report-section">
        <h3 style={{ marginBottom: 16 }}>基线密码资产快照（{assets.length}）</h3>
        {assets.length > 0 ? (
          <Collapse
            items={[{
              key: 'assets',
              label: `共 ${assets.length} 项密码资产`,
              children: (
                <Table
                  dataSource={assets}
                  columns={assetColumns}
                  rowKey="key"
                  size="small"
                  pagination={assets.length > 20 ? { pageSize: 20 } : false}
                />
              ),
            }]}
          />
        ) : (
          <Empty description="基线无密码资产" />
        )}
      </div>

      <Modal
        title="生成差异报告"
        open={modalOpen}
        onOk={handleGenerate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={generating}
        destroyOnClose
      >
        <p style={{ marginBottom: 12 }}>选择一个已完成的分析任务，与当前基线对比生成密码资产差异。仅显示代码路径与语言均与基线一致的任务。</p>
        <Select
          style={{ width: '100%' }}
          placeholder="选择已完成的分析任务"
          showSearch
          optionFilterProp="label"
          onChange={setSelectedTask}
          notFoundContent="无与基线项目一致的已完成分析任务"
          options={completedTasks.map((t) => ({
            value: t.id,
            label: `#${t.id} ${t.name} (${t.language?.toUpperCase()})`,
          }))}
        />
      </Modal>
    </div>
  )
}
