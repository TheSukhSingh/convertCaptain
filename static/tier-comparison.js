
document.addEventListener('DOMContentLoaded', function() {

    const plusPrice = document.getElementById('plus-price');
    const proPrice = document.getElementById('pro-price');
    
    // Monthly prices (default)
    const monthlyPrices = {
      plus: '$4.99',
      pro: '$9.99'
    };
    
    // Annual prices (20% discount)
    const annualPrices = {
      plus: '$7.99',
      pro: '$15.99'
    };
    
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
      const question = item.querySelector('.faq-question');
      
      question.addEventListener('click', function() {
        // Close other open FAQ items
        faqItems.forEach(otherItem => {
          if (otherItem !== item && otherItem.classList.contains('active')) {
            otherItem.classList.remove('active');
          }
        });
        
        // Toggle current item
        item.classList.toggle('active');
      });
    });
    
    // Button click handlers
    const pricingButtons = document.querySelectorAll('.pricing-btn');
    
    pricingButtons.forEach(button => {
      button.addEventListener('click', function() {
        const plan = this.closest('.pricing-card').querySelector('h2').textContent;
        
        if (this.textContent === 'Current Plan') {
          showToast(`You're already on the ${plan} plan`, 'info');
        } else {
          showToast(`Upgrading to ${plan} plan`, 'success');
        }
      });
    });
  });