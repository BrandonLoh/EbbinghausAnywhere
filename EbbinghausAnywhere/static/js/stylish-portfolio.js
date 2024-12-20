(function() {
  "use strict"; // Start of use strict

  var menuToggle = document.querySelector('.menu-toggle');
  var sidebar = document.querySelector('#sidebar-wrapper');
  
  if (menuToggle) {
    // Closes the sidebar menu
    console.log("Menu toggle found:", menuToggle); // 调试输出：是否找到menuToggle按钮
    
    menuToggle.addEventListener('click', function(e) {
      e.preventDefault();
      
      console.log("Menu toggle clicked"); // 调试输出：按钮是否被点击

      // Toggle active state for sidebar and button
      sidebar.classList.toggle('active');
      menuToggle.classList.toggle('active');
      
      // 调试输出：sidebar和menuToggle的当前状态
      console.log("Sidebar active:", sidebar.classList.contains('active'));
      console.log("Menu toggle active:", menuToggle.classList.contains('active'));
      
      // Get the icon inside the button
      var icon = menuToggle.querySelector('.fa-bars, .fa-times');
      console.log("Icon found:", icon); // 调试输出：是否找到了图标

      if (icon) {
        // Switch between fa-bars and fa-times icon
        if (icon.classList.contains('fa-times')) {
          console.log("Switching icon from fa-times to fa-bars"); // 调试输出：切换图标
          icon.classList.remove('fa-times');
          icon.classList.add('fa-bars');
        } else {
          console.log("Switching icon from fa-bars to fa-times"); // 调试输出：切换图标
          icon.classList.remove('fa-bars');
          icon.classList.add('fa-times');
        }
      }
    });
  } else {
    console.log("Menu toggle not found"); // 调试输出：没有找到menuToggle按钮
  }

  var navbarCollapse = document.querySelector('.navbar-collapse');
  console.log("Navbar collapse:", navbarCollapse); // 调试输出：是否找到navbar-collapse

  if (navbarCollapse) {
    var navbarItems = navbarCollapse.querySelectorAll('a');
    console.log("Navbar items:", navbarItems); // 调试输出：navbar中所有的链接

    // Closes responsive menu when a scroll trigger link is clicked
    for (var item of navbarItems) {
      item.addEventListener('click', function (event) {
        console.log("Navbar item clicked:", event.target); // 调试输出：点击的菜单项

        sidebar.classList.remove('active');
        menuToggle.classList.remove('active');
        
        var icon = menuToggle.querySelector('.fa-bars, .fa-times');
        
        if (icon) {
          if (icon.classList.contains('fa-times')) {
            console.log("Switching icon from fa-times to fa-bars (after menu item click)"); // 调试输出：点击菜单项后切换图标
            icon.classList.remove('fa-times');
            icon.classList.add('fa-bars');
          } else {
            console.log("Switching icon from fa-bars to fa-times (after menu item click)"); // 调试输出：点击菜单项后切换图标
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-times');
          }
        }
      });
    }
  }

  // Scroll to top button appear
  var scrollToTop = document.querySelector('.scroll-to-top');
  
  if (scrollToTop) {
    window.addEventListener('scroll', function() {
      var scrollDistance = window.pageYOffset;

      if (scrollDistance > 100) {
        scrollToTop.style.display = 'block';
      } else {
        scrollToTop.style.display = 'none';
      }
    });
  }

})(); // End of use strict

// Disable Google Maps scrolling (optional)
var onMapMouseleaveHandler = function(e) {
  this.addEventListener('click', onMapClickHandler);
  this.removeEventListener('mouseleave', onMapMouseleaveHandler);

  var iframe = this.querySelector('iframe'); 
  
  if (iframe) {
    iframe.style.pointerEvents = 'none';
  }
}

var onMapClickHandler = function(e) {
  this.removeEventListener('click', onMapClickHandler);
  this.addEventListener('mouseleave', onMapMouseleaveHandler);

  var iframe = this.querySelector('iframe'); 
  
  if (iframe) {
    iframe.style.pointerEvents = 'auto';
  }
}

var maps = document.querySelectorAll('.map');

for (var map of maps) {
  map.addEventListener('click', onMapClickHandler);
}
