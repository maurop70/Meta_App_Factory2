import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Catch errors in any components below and re-render with error message
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // Fallback UI
      return (
        <div style={{
          padding: '20px',
          backgroundColor: '#3f0000',
          color: '#ffaaaa',
          fontFamily: 'monospace',
          borderRadius: '8px',
          border: '1px solid #ff0000',
          margin: '20px'
        }}>
          <h2>💥 FATAL COMPONENT FRACTURE</h2>
          <p>The neural pathway has encountered an unhandled exception.</p>
          <hr style={{ borderColor: '#ff0000' }} />
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em' }}>
            {this.state.error && this.state.error.toString()}
            <br />
            {this.state.errorInfo && this.state.errorInfo.componentStack}
          </pre>
        </div>
      );
    }
    // Normally, just render children
    return this.props.children;
  }
}

export default ErrorBoundary;
