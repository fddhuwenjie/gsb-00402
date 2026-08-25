import { Table, Button, Tag, Tooltip, Popconfirm, message } from 'antd'
import { PlusOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { analysisApi } from '../api/client'

const statusMap = {
  pending: { color: 'default', text: '等待中' },
  running: { color: 'processing', text: '运行中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
}

export default function AnalysesPage() {
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
      const res = await analysisApi.list(p)
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page])

  const handleDelete = async (id) => {
    await analysisApi.delete(id)
    message.success('删除成功')
    fetchData()
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 55, fixed: 'left' },
    { title: '任务名称', dataIndex: 'name', width: 200, ellipsis: true },
    {
      title: '语言', dataIndex: 'language', width: 70, align: 'center',
      render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 90, align: 'center',
      render: (v) => {
        const s = statusMap[v] || { color: 'default', text: v }
        return <Tag color={s.color}>{s.text}</Tag>
      },
    },
    {
      title: '特征文件', dataIndex: 'signature_file_names', width: 160, ellipsis: true,
      render: (names) => names?.map((n, i) => <Tag key={i} style={{ marginBottom: 2 }}>{n}</Tag>),
    },
    { title: '创建者', dataIndex: 'creator_name', width: 90 },
    {
      title: '创建时间', dataIndex: 'created_at', width: 180,
      render: (v) => <span style={{ whiteSpace: 'nowrap' }}>{dayjs(v).format('YYYY-MM-DD HH:mm:ss')}</span>,
    },
    {
      title: '操作', width: 100, align: 'center', fixed: 'right',
      render: (_, record) => (
        <span style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Tooltip title="查看详情">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/analyses/${record.id}`)} />
          </Tooltip>
          {isAdmin && (
            <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
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
        <h2>分析任务</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/analyses/new')}>
          新建分析
        </Button>
      </div>

      <div style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 900 }}
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
