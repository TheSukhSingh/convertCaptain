document.addEventListener('DOMContentLoaded', function() {
  // Initialize the activity chart
  const activityCtx = document.getElementById('activity-chart').getContext('2d');
  
  // Get last 7 days for labels
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    days.push(date.toLocaleDateString('en-US', { weekday: 'short' }));
  }
  
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
        pointRadius: 4,
        pointHoverRadius: 6,
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
            stepSize: 5
          }
        },
        x: {
          grid: {
            display: false
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
          padding: 10,
          titleFont: {
            size: 14,
            weight: 'bold'
          },
          bodyFont: {
            size: 13
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

  // Animation for stats
  const animateStats = () => {
    const statValues = document.querySelectorAll('.stat-value');
    
    statValues.forEach((stat) => {
      const finalValue = stat.textContent;
      let startValue = 0;
      
      if (finalValue.includes('sec')) {
        const numValue = parseFloat(finalValue);
        startValue = 0;
        
        const counter = setInterval(() => {
          if (startValue < numValue) {
            startValue += 0.1;
            stat.textContent = startValue.toFixed(1) + ' sec';
          } else {
            clearInterval(counter);
            stat.textContent = finalValue;
          }
        }, 50);
      } else {
        const numValue = parseInt(finalValue);
        
        const counter = setInterval(() => {
          if (startValue < numValue) {
            startValue++;
            stat.textContent = startValue;
          } else {
            clearInterval(counter);
          }
        }, 100);
      }
    });
  };

  // Toast notification function
  const showToast = (message, type = 'info') => {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    toastContainer.appendChild(toast);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
      toast.style.animation = 'slide-out 0.3s forwards';
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, 3000);
  };

  // Create toast container if it doesn't exist
  const createToastContainer = () => {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
  };

  // Initialize animations
  animateStats();
  
  // Stagger animations for smoother loading
  setTimeout(() => {
    document.querySelectorAll('.profile-section').forEach((section, index) => {
      setTimeout(() => {
        section.style.opacity = '1';
        section.style.transform = 'translateY(0)';
      }, index * 100);
    });
  }, 300);
  
  // Handle button click events
  document.querySelectorAll('.btn').forEach(button => {
    button.addEventListener('click', function(e) {
      if (this.classList.contains('manage-btn')) {
        e.preventDefault();
        showToast('Subscription management coming soon!', 'info');
      }
    });
  });

  // Links for demo purposes
  document.querySelectorAll('.recommendation-link, .view-all-link').forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      showToast('This feature will be available soon!', 'info');
    });
  });
});
