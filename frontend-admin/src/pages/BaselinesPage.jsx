import { Table, Button, Tag, Tooltip, Popconfirm, message, Modal, Form, Input, Select } from 'antd'
import { PlusOutlined, EyeOutlined, DeleteOutlined, DiffOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi, analysisApi } from '../api/client'

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

export default function BaselinesPage() {
  const navigate = useNavigate()
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [tasks, setTasks] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()
  const isAdmin = (() => {
    try { return JSON.parse(localStorage.getItem('user'))?.role === 'admin' } catch { return false }
  })()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await baselineApi.list(p)
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  const fetchCompletedTasks = async () => {
    const res = await analysisApi.list(1, 100)
    const completed = res.data.items.filter((t) => t.status === 'completed')
    setTasks(completed)
  }

  useEffect(() => { fetchData() }, [page])

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const res = await baselineApi.create({
        name: values.name,
        description: values.description || '',
        task_id: values.task_id,
      })
      message.success('基线保存成功')
      setModalOpen(false)
      form.resetFields()
      navigate(`/baselines/${res.data.id}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    await baselineApi.delete(id)
    message.success('删除成功')
    fetchData()
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 55, fixed: 'left' },
    { title: '基线名称', dataIndex: 'name', width: 200, ellipsis: true },
    {
      title: '语言', dataIndex: 'language', width: 70, align: 'center',
      render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
    },
    {
      title: '来源分析', dataIndex: 'task_name', width: 180, ellipsis: true,
      render: (v, r) => <a onClick={() => navigate(`/analyses/${r.task_id}`)}>{v || `#${r.task_id}`}</a>,
    },
    { title: '密码资产数', dataIndex: 'total_assets', width: 100, align: 'center' },
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
      title: '操作', width: 130, align: 'center', fixed: 'right',
      render: (_, record) => (
        <span style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Tooltip title="查看基线详情">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/baselines/${record.id}`)} />
          </Tooltip>
          <Tooltip title="基于此基线生成差异报告">
            <Button type="text" size="small" icon={<DiffOutlined />} onClick={() => navigate(`/diffs/new?baseline_id=${record.id}`)} />
          </Tooltip>
          {isAdmin && (
            <Popconfirm title="确定删除该基线？关联的差异报告将一并删除" onConfirm={() => handleDelete(record.id)}>
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
        <h2>分析基线</h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => { fetchCompletedTasks(); setModalOpen(true) }}
        >
          保存基线
        </Button>
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1000 }}
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
        title="保存分析基线"
        open={modalOpen}
        onOk={handleCreate}
        confirmLoading={submitting}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="task_id"
            label="选择已完成的分析任务"
            rules={[{ required: true, message: '请选择分析任务' }]}
          >
            <Select
              placeholder="选择分析任务"
              showSearch
              optionFilterProp="label"
              options={tasks.map((t) => ({
                label: `#${t.id} ${t.name}（${t.language?.toUpperCase()}）`,
                value: t.id,
              }))}
              onChange={(taskId) => {
                const t = tasks.find((x) => x.id === taskId)
                if (t && !form.getFieldValue('name')) {
                  form.setFieldsValue({ name: `${t.name} - 基线` })
                }
              }}
            />
          </Form.Item>
          <Form.Item name="name" label="基线名称" rules={[{ required: true, message: '请输入基线名称' }]}>
            <Input placeholder="例如：v1.0 发布基线" maxLength={200} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="可选说明" maxLength={1000} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
