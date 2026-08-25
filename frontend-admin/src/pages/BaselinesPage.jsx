import { Table, Button, Tag, Tooltip, Popconfirm, message, Typography } from 'antd'
import { EyeOutlined, DeleteOutlined, DiffOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi, diffApi } from '../api/client'

const { Text } = Typography

export default function BaselinesPage() {
  const navigate = useNavigate()
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
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

  useEffect(() => { fetchData() }, [page])

  const handleDelete = async (id) => {
    await baselineApi.delete(id)
    message.success('基线已删除')
    fetchData()
  }

  const handleCompare = async (record) => {
    const taskId = prompt(`请输入要与基线「${record.name}」对比的已完成分析任务 ID：`)
    if (!taskId) return
    const tid = Number(taskId)
    if (!Number.isInteger(tid) || tid <= 0) {
      message.error('请输入有效的任务 ID')
      return
    }
    try {
      const res = await diffApi.create({ baseline_id: record.id, task_id: tid })
      message.success('差异报告已生成')
      navigate(`/diffs/${res.data.id}`)
    } catch { /* handled by interceptor */ }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 55, fixed: 'left' },
    { title: '基线名称', dataIndex: 'name', width: 220, ellipsis: true },
    {
      title: '语言', dataIndex: 'language', width: 80, align: 'center',
      render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
    },
    {
      title: '资产数', dataIndex: 'asset_count', width: 80, align: 'center',
      render: (v) => <Tag color="purple">{v}</Tag>,
    },
    { title: '项目标识', dataIndex: 'project_key', width: 140, ellipsis: true, render: (v) => v ? <Text code style={{ fontSize: 12 }}>{v}</Text> : '-' },
    { title: '代码路径', dataIndex: 'code_path', ellipsis: true, render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text> },
    { title: '来源任务', dataIndex: 'source_task_name', width: 110 },
    { title: '创建者', dataIndex: 'creator_name', width: 90 },
    {
      title: '创建时间', dataIndex: 'created_at', width: 170,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 130, align: 'center', fixed: 'right',
      render: (_, record) => (
        <span style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Tooltip title="查看基线">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/baselines/${record.id}`)} />
          </Tooltip>
          <Tooltip title="与分析任务对比">
            <Button type="text" size="small" icon={<DiffOutlined />} onClick={() => handleCompare(record)} />
          </Tooltip>
          {isAdmin && (
            <Popconfirm title="确定删除该基线？" onConfirm={() => handleDelete(record.id)}>
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
        <Button onClick={() => navigate('/analyses')}>前往分析任务保存基线</Button>
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
    </div>
  )
}
