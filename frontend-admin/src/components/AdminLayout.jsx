import { Layout, Menu, Avatar, Dropdown, Typography, Tag } from 'antd'
import {
  DashboardOutlined,
  FileSearchOutlined,
  ExperimentOutlined,
  UserOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  DiffOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect, useMemo } from 'react'
import { authApi } from '../api/client'

const { Header, Sider, Content } = Layout

export default function AdminLayout({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
  })

  useEffect(() => {
    authApi.me().then((res) => {
      setUser(res.data)
      localStorage.setItem('user', JSON.stringify(res.data))
    }).catch(() => {})
  }, [])

  const isAdmin = user?.role === 'admin'

  const menuItems = useMemo(() => {
    const items = [
      { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
      { key: '/signatures', icon: <FileSearchOutlined />, label: '特征管理' },
      { key: '/analyses', icon: <ExperimentOutlined />, label: '分析任务' },
      { key: '/baselines', icon: <DiffOutlined />, label: '基线与差异' },
    ]
    if (isAdmin) {
      items.push({ key: '/users', icon: <TeamOutlined />, label: '用户管理' })
    }
    return items
  }, [isAdmin])

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const selectedKey = '/' + location.pathname.split('/')[1]

  const dropdownItems = {
    items: [
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true, onClick: handleLogout },
    ],
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          <SafetyCertificateOutlined style={{ fontSize: 28, color: '#1677ff' }} />
          {!collapsed && (
            <Typography.Text strong style={{ color: 'white', marginLeft: 10, fontSize: 16 }}>
              CBOM Analyzer
            </Typography.Text>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: 8 }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.2s' }}>
        <Header style={{
          background: 'white',
          padding: '0 24px',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}>
          <Dropdown menu={dropdownItems} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar
                icon={<UserOutlined />}
                style={{ backgroundColor: isAdmin ? '#722ed1' : '#1677ff' }}
              />
              <span style={{ color: '#333', fontWeight: 500 }}>{user?.username || '...'}</span>
              {isAdmin && <Tag color="purple" style={{ marginLeft: 2 }}>Admin</Tag>}
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, minHeight: 'calc(100vh - 112px)' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
