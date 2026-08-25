import { Table, Button, Tag, Tooltip, Popconfirm, message, Modal, Form, Input, Select } from 'antd'
import { PlusOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import { diffApi, baselineApi, analysisApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

export default function DiffsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const presetBaselineId = searchParams.get('baseline_id')

  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [baselines, setBaselines] = useState([])
  const [tasks, setTasks] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()
  const isAdmin = (() => {
    try { return JSON.parse(localStorage.getItem('user'))?.role === 'admin' } catch { return false }
  })()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await diffApi.list(p)
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  const openModal = async () => {
    const [bRes, tRes] = await Promise.all([
      baselineApi.list(1, 200),
      analysisApi.list(1, 200),
    ])
    setBaselines(bRes.data.items)
    setTasks(tRes.data.items.filter((t) => t.status === 'completed'))
    form.resetFields()
    if (presetBaselineId) {
      form.setFieldsValue({ baseline_id: Number(presetBaselineId) })
    }
    setModalOpen(true)
  }

  useEffect(() => { fetchData() }, [page])

  useEffect(() => {
    if (presetBaselineId) openModal()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetBaselineId])

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const res = await diffApi.create({
        name: values.name || '',
        baseline_id: values.baseline_id,
        task_id: values.task_id,
      })
      message.success('差异报告生成成功')
      setModalOpen(false)
      navigate(`/diffs/${res.data.id}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    await diffApi.delete(id)
    message.success('删除成功')
    fetchData()
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 55, fixed: 'left' },
    { title: '报告名称', dataIndex: 'name', width: 240, ellipsis: true },
    {
      title: '基线', dataIndex: 'baseline_name', width: 160, ellipsis: true,
      render: (v, r) => <a onClick={() => navigate(`/baselines/${r.baseline_id}`)}>{v || `#${r.baseline_id}`}</a>,
    },
    {
      title: '对比分析', dataIndex: 'task_name', width: 160, ellipsis: true,
      render: (v, r) => <a onClick={() => navigate(`/analyses/${r.task_id}`)}>{v || `#${r.task_id}`}</a>,
    },
    {
      title: '新增', dataIndex: 'added_count', width: 80, align: 'center',
      render: (v) => <Tag color={v > 0 ? 'green' : 'default'}>+{v}</Tag>,
    },
    {
      title: '移除', dataIndex: 'removed_count', width: 80, align: 'center',
      render: (v) => <Tag color={v > 0 ? 'red' : 'default'}>-{v}</Tag>,
    },
    {
      title: '变化', dataIndex: 'changed_count', width: 80, align: 'center',
      render: (v) => <Tag color={v > 0 ? 'orange' : 'default'}>~{v}</Tag>,
    },
    {
      title: '风险级别', dataIndex: 'risk_level', width: 90, align: 'center',
      render: (v) => <Tag color={riskColors[v] || 'default'}>{riskLabels[v] || v}</Tag>,
    },
    { title: '创建者', dataIndex: 'creator_name', width: 90 },
    {
      title: '创建时间', dataIndex: 'created_at', width: 170,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 80, align: 'center', fixed: 'right',
      render: (_, record) => (
        <span style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Tooltip title="查看差异详情">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/diffs/${record.id}`)} />
          </Tooltip>
          {isAdmin && (
            <Popconfirm title="确定删除该差异报告？" onConfirm={() => handleDelete(record.id)}>
              <Tooltip title="删除">
                <Button type="text" danger size="small" icon={<DeleteOutlined />} />
              </Tooltip>
            </Popconfirm>
          )}
        </span>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>差异报告</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>
          生成差异报告
        </Button>
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </div>

      <Modal
        title="生成差异报告"
        open={modalOpen}
        onOk={handleCreate}
        confirmLoading={submitting}
        onCancel={() => setModalOpen(false)}
        okText="生成"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="baseline_id"
            label="选择基线"
            rules={[{ required: true, message: '请选择基线' }]}
          >
            <Select
              placeholder="选择已保存的基线"
              showSearch
              optionFilterProp="label"
              options={baselines.map((b) => ({
                label: `#${b.id} ${b.name}（${b.language?.toUpperCase()}，${b.total_assets} 资产）`,
                value: b.id,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="task_id"
            label="选择当前分析（对比项）"
            rules={[{ required: true, message: '请选择分析任务' }]}
          >
            <Select
              placeholder="选择已完成的分析任务"
              showSearch
              optionFilterProp="label"
              options={tasks.map((t) => ({
                label: `#${t.id} ${t.name}（${t.language?.toUpperCase()}）`,
                value: t.id,
              }))}
            />
          </Form.Item>
          <Form.Item name="name" label="报告名称（可选）">
            <Input placeholder="留空则自动命名" maxLength={200} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
