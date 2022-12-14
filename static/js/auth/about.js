'use strict';

const root = document.documentElement;
                const allButtons = document.querySelectorAll('button')
                
                function buttonClick(event) {
                    let btn = event.target;
                    btn.classList.toggle('open')
                    btn.nextElementSibling.classList.toggle('open')
                    root.style.setProperty('--content-height', btn.nextElementSibling.scrollHeight + 'px');
                    allButtons.forEach(button => {
                        if (button !== btn) {
                            button.classList.remove('open')
                            button.nextElementSibling.classList.remove('open')
                        }
                    })
                }
                
                allButtons.forEach(element => {
                    element.addEventListener('click', buttonClick)
                });

