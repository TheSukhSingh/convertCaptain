document.addEventListener('DOMContentLoaded', function() {
  // Check if we're on a mobile device
  const isMobile = window.innerWidth <= 768;
  
  // Initialize the activity chart
  const activityCtx = document.getElementById('activity-chart').getContext('2d');
  
  // Get last 7 days for labels
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    days.push(date.toLocaleDateString('en-US', { weekday: isMobile ? 'short' : 'short' }));
  }
  
  // Create chart with responsive options
  const activityChart = new Chart(activityCtx, {
    type: 'line',
    data: {
      labels: days,
      datasets: [{
        label: 'Conversions',
        data: window.userConversionData || [0, 0, 0, 0, 0, 0, 0],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 3,
        tension: 0.3,
        pointBackgroundColor: '#3b82f6',
        pointRadius: isMobile ? 3 : 4,
        pointHoverRadius: isMobile ? 5 : 6,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            display: true,
            color: 'rgba(0, 0, 0, 0.05)'
          },
          ticks: {
            stepSize: 5,
            font: {
              size: isMobile ? 10 : 12
            }
          }
        },
        x: {
          grid: {
            display: false
          },
          ticks: {
            font: {
              size: isMobile ? 10 : 12
            }
          }
        }
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          titleColor: '#1e293b',
          bodyColor: '#64748b',
          borderColor: '#e2e8f0',
          borderWidth: 1,
          padding: isMobile ? 8 : 10,
          titleFont: {
            size: isMobile ? 12 : 14,
            weight: 'bold'
          },
          bodyFont: {
            size: isMobile ? 11 : 13
          },
          callbacks: {
            title: function(items) {
              return items[0].label;
            },
            label: function(item) {
              return `${item.formattedValue} conversions`;
            }
          }
        }
      }
    }
  });

  // Handle window resize for chart responsiveness
  window.addEventListener('resize', function() {
    const newIsMobile = window.innerWidth <= 768;
    if (newIsMobile !== isMobile) {
      location.reload(); // Refresh the page to rebuild the chart with appropriate settings
    }
  });

  // Animation for stats with different speed based on device
  const animateStats = () => {
    const statValues = document.querySelectorAll('.stat-value');
    const animationSpeed = isMobile ? 30 : 50;
    
    statValues.forEach((stat) => {
      const finalValue = stat.textContent;
      
      if (!isNaN(parseInt(finalValue))) {
        const numValue = parseInt(finalValue);
        let startValue = 0;
        
        // Adjust increment based on the final value
        const increment = Math.max(1, Math.floor(numValue / 20));
        
        const counter = setInterval(() => {
          if (startValue < numValue) {
            startValue += increment;
            if (startValue > numValue) startValue = numValue;
            stat.textContent = startValue;
          } else {
            clearInterval(counter);
          }
        }, animationSpeed);
      }
    });
  };

  // Toast notification function with mobile adaptations
  const showToast = (message, type = 'info') => {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    toastContainer.appendChild(toast);
    
    // Shorter display time on mobile
    const displayTime = isMobile ? 2500 : 3000;
    
    setTimeout(() => {
      toast.style.animation = 'slide-out 0.3s forwards';
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, displayTime);
  };

  // Create toast container if it doesn't exist
  const createToastContainer = () => {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
  };

  // Initialize animations with a small delay
  setTimeout(() => {
    animateStats();
  }, 300);
  
  // Stagger animations for smoother loading with faster timing on mobile
  const staggerDelay = isMobile ? 80 : 100;
  setTimeout(() => {
    document.querySelectorAll('.profile-section').forEach((section, index) => {
      setTimeout(() => {
        section.style.opacity = '1';
        section.style.transform = 'translateY(0)';
      }, index * staggerDelay);
    });
  }, 200);
  
  // Handle button click events
  document.querySelectorAll('.btn').forEach(button => {
    button.addEventListener('click', function(e) {
      if (this.classList.contains('manage-btn')) {
        e.preventDefault();
        showToast('Subscription management coming soon!', 'info');
      }
    });
  });

  // Add touch-friendly interactions for mobile
  if (isMobile) {
    document.querySelectorAll('.tip-item').forEach(item => {
      item.addEventListener('touchstart', function() {
        this.style.backgroundColor = '#f1f5f9';
      });
      
      item.addEventListener('touchend', function() {
        setTimeout(() => {
          this.style.backgroundColor = '#f8fafc';
        }, 100);
      });
    });
    
    document.querySelectorAll('.metric-item').forEach(item => {
      item.addEventListener('touchstart', function() {
        this.style.transform = 'translateY(-2px)';
      });
      
      item.addEventListener('touchend', function() {
        setTimeout(() => {
          this.style.transform = 'translateY(0)';
        }, 100);
      });
    });
  }
});
