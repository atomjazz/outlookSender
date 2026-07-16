const editor = document.getElementById('editor');
let backendObj = null;

// Apply text formatting commands
function formatDoc(cmd, value = null) {
    document.execCommand(cmd, false, value);
    editor.focus();
    notifyContentChanged();
}

// Initialize QWebChannel bridge with Python
if (typeof qt !== 'undefined') {
    new QWebChannel(qt.webChannelTransport, function (channel) {
        backendObj = channel.objects.backend;
        
        // Connect python signals/methods
        if (backendObj) {
            backendObj.setHtmlText.connect(function(html) {
                setHtml(html);
            });
        }
    });
} else {
    console.log("QWebChannel 'qt' transport is not defined (running outside of QWebEngineView).");
}

function getHtml() {
    return editor.innerHTML;
}

function setHtml(html) {
    editor.innerHTML = html;
}

let isConverting = false;
async function convertLocalImagesToBase64() {
    if (isConverting) return false;
    isConverting = true;
    
    const imgs = editor.querySelectorAll('img, imagedata, v\\:imagedata');
    let changed = false;
    for (let img of imgs) {
        const src = img.getAttribute('src');
        if (src && src.startsWith('file://')) {
            try {
                const response = await fetch(src);
                const blob = await response.blob();
                const base64 = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
                img.setAttribute('src', base64);
                changed = true;
            } catch (e) {
                console.error("Failed to convert local image to base64:", src, e);
            }
        }
    }
    
    isConverting = false;
    return changed;
}

function notifyContentChanged() {
    convertLocalImagesToBase64().then(function(changed) {
        if (backendObj && backendObj.on_content_changed) {
            backendObj.on_content_changed(getHtml());
        }
    });
}

// Event listeners to detect modifications
editor.addEventListener('input', notifyContentChanged);
editor.addEventListener('blur', notifyContentChanged);
editor.addEventListener('keyup', notifyContentChanged);
editor.addEventListener('paste', function() {
    setTimeout(notifyContentChanged, 100);
});

// Drag & Drop Placeholders logic
editor.addEventListener('dragover', function(e) {
    e.preventDefault();
});

editor.addEventListener('drop', function(e) {
    // 1. Handle local file drop (read image as Base64 Data URL)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        e.preventDefault();
        const files = e.dataTransfer.files;
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (file.type.startsWith("image/")) {
                const reader = new FileReader();
                reader.onload = function(evt) {
                    const base64Src = evt.target.result;
                    
                    let range;
                    if (document.caretRangeFromPoint) {
                        range = document.caretRangeFromPoint(e.clientX, e.clientY);
                    } else if (e.rangeParent) {
                        range = document.createRange();
                        range.setStart(e.rangeParent, e.rangeOffset);
                    }
                    
                    if (range) {
                        const sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        const img = document.createElement("img");
                        img.src = base64Src;
                        img.style.maxWidth = "100%";
                        img.style.height = "auto";
                        
                        range.insertNode(img);
                        sel.removeAllRanges();
                        notifyContentChanged();
                    }
                };
                reader.readAsDataURL(file);
            }
        }
        return;
    }

    // 2. Handle placeholder text drag and drop
    e.preventDefault();
    const data = e.dataTransfer.getData("text/plain");
    
    if (data && data.startsWith("{{") && data.endsWith("}}")) {
        let range = null;
        if (document.caretRangeFromPoint) {
            range = document.caretRangeFromPoint(e.clientX, e.clientY);
        } else if (e.rangeParent) {
            range = document.createRange();
            range.setStart(e.rangeParent, e.rangeOffset);
        }
        
        if (range) {
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            
            // Create the placeholder badge
            const span = document.createElement("span");
            span.className = "placeholder-badge";
            span.setAttribute("contenteditable", "false");
            span.innerText = data;
            
            // Insert trailing space for continuous typing
            const spaceNode = document.createTextNode(" ");
            
            range.insertNode(spaceNode);
            range.insertNode(span);
            
            // Clean up selection and trigger notification
            sel.removeAllRanges();
            notifyContentChanged();
        }
    }
});

// Table Column & Row Resizing Logic
(function() {
    let activeTd = null;
    let resizeType = null; // 'col' or 'row'
    let startX = 0, startY = 0;
    let startWidth = 0, startHeight = 0;

    editor.addEventListener('mousemove', function(e) {
        if (activeTd) return; // Ignore if actively resizing

        let target = e.target;
        while (target && target !== editor && target.tagName !== 'TD' && target.tagName !== 'TH') {
            target = target.parentElement;
        }

        if (!target || target === editor) {
            editor.style.cursor = 'default';
            return;
        }

        const rect = target.getBoundingClientRect();
        const borderDistRight = rect.right - e.clientX;
        const borderDistBottom = rect.bottom - e.clientY;

        // 1. Column Resizing (Right Border)
        if (borderDistRight >= 0 && borderDistRight <= 6) {
            target.style.cursor = 'col-resize';
            target.setAttribute('data-resize-hover', 'col');
        } 
        // 2. Row Resizing (Bottom Border)
        else if (borderDistBottom >= 0 && borderDistBottom <= 6) {
            target.style.cursor = 'row-resize';
            target.setAttribute('data-resize-hover', 'row');
        } else {
            target.style.cursor = 'default';
            target.removeAttribute('data-resize-hover');
        }
    });

    editor.addEventListener('mousedown', function(e) {
        let target = e.target;
        while (target && target !== editor && target.tagName !== 'TD' && target.tagName !== 'TH') {
            target = target.parentElement;
        }

        const hoverType = target ? target.getAttribute('data-resize-hover') : null;
        if (target && hoverType) {
            e.preventDefault();
            activeTd = target;
            resizeType = hoverType;
            startX = e.clientX;
            startY = e.clientY;
            startWidth = target.offsetWidth;
            startHeight = target.offsetHeight;

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        }
    });

    function onMouseMove(e) {
        if (!activeTd) return;
        if (resizeType === 'col') {
            const diffX = e.clientX - startX;
            const newWidth = Math.max(30, startWidth + diffX);
            activeTd.style.width = newWidth + 'px';
            activeTd.width = newWidth;
        } else if (resizeType === 'row') {
            const diffY = e.clientY - startY;
            const newHeight = Math.max(20, startHeight + diffY);
            activeTd.style.height = newHeight + 'px';
            activeTd.height = newHeight;
        }
    }

    function onMouseUp() {
        if (activeTd) {
            activeTd.removeAttribute('data-resize-hover');
            activeTd.style.cursor = 'default';
            activeTd = null;
            resizeType = null;
            notifyContentChanged();
        }
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }
})();

// Table Toolbar Helper Actions
function getActiveCell() {
    const sel = window.getSelection();
    if (sel.rangeCount === 0) return null;
    let node = sel.getRangeAt(0).startContainer;
    while (node && node !== editor) {
        if (node.tagName === 'TD' || node.tagName === 'TH') {
            return node;
        }
        node = node.parentNode;
    }
    return null;
}

function insertTable() {
    const tableHtml = '<table border="1" style="border-collapse: collapse; width: 100%; border-color: #d1d1d6; margin-bottom: 12px;">' +
        '<tbody>' +
        '  <tr><td style="padding: 6px;">&nbsp;</td><td style="padding: 6px;">&nbsp;</td><td style="padding: 6px;">&nbsp;</td></tr>' +
        '  <tr><td style="padding: 6px;">&nbsp;</td><td style="padding: 6px;">&nbsp;</td><td style="padding: 6px;">&nbsp;</td></tr>' +
        '</tbody>' +
        '</table><p>&nbsp;</p>';
    document.execCommand('insertHTML', false, tableHtml);
    notifyContentChanged();
}

function insertRow() {
    const cell = getActiveCell();
    if (!cell) return;
    const row = cell.parentElement;
    const tbody = row.parentElement;
    const newRow = row.cloneNode(true);
    
    // Clear content of new cells
    newRow.querySelectorAll('td, th').forEach(c => {
        c.innerHTML = '&nbsp;';
        c.style.height = ''; // Reset row height on cloned row
    });
    
    row.after(newRow);
    notifyContentChanged();
}

function deleteRow() {
    const cell = getActiveCell();
    if (!cell) return;
    const row = cell.parentElement;
    const tbody = row.parentElement;
    row.remove();
    notifyContentChanged();
}

function insertColumn() {
    const cell = getActiveCell();
    if (!cell) return;
    const index = cell.cellIndex;
    const table = cell.closest('table');
    
    table.querySelectorAll('tr').forEach(row => {
        const cells = row.querySelectorAll('td, th');
        const refCell = cells[index];
        const newCell = document.createElement(refCell.tagName);
        newCell.innerHTML = '&nbsp;';
        newCell.style.padding = '6px';
        refCell.after(newCell);
    });
    notifyContentChanged();
}

function deleteColumn() {
    const cell = getActiveCell();
    if (!cell) return;
    const index = cell.cellIndex;
    const table = cell.closest('table');
    
    table.querySelectorAll('tr').forEach(row => {
        const cells = row.querySelectorAll('td, th');
        if (cells[index]) {
            cells[index].remove();
        }
    });
    notifyContentChanged();
}

// ----------------------------------------------------
// Image and Table Resizing Overlay Systems
// ----------------------------------------------------

let currentImage = null;
let resizerOverlay = null;

let currentTable = null;
let currentCell = null;
let currentRow = null;
let tableResizerOverlay = null;

// Global Click listener for detecting click on images or tables
editor.addEventListener('click', function(e) {
    var target = e.target;
    
    // 1. Check Image Click
    if (target.tagName && (target.tagName.toLowerCase() === 'img' || target.tagName.toLowerCase() === 'imagedata')) {
        hideTableResizer();
        showImageResizer(target);
        return;
    }
    hideImageResizer();
    
    // 2. Check Table/Cell Click
    var cell = target.closest('td, th');
    if (cell) {
        var table = cell.closest('table');
        var row = cell.closest('tr');
        if (table && row) {
            showTableResizer(table, cell, row);
            return;
        }
    }
    hideTableResizer();
});

// Image Resizer Overlay Setup and Positioners
function showImageResizer(img) {
    currentImage = img;
    
    if (!resizerOverlay) {
        resizerOverlay = document.createElement('div');
        resizerOverlay.id = 'image-resizer-overlay';
        resizerOverlay.style.position = 'absolute';
        resizerOverlay.style.background = 'rgba(30, 30, 30, 0.95)';
        resizerOverlay.style.color = '#ffffff';
        resizerOverlay.style.padding = '8px 12px';
        resizerOverlay.style.borderRadius = '6px';
        resizerOverlay.style.boxShadow = '0 4px 12px rgba(0,0,0,0.25)';
        resizerOverlay.style.display = 'flex';
        resizerOverlay.style.alignItems = 'center';
        resizerOverlay.style.gap = '8px';
        resizerOverlay.style.zIndex = '1000';
        resizerOverlay.style.fontSize = '12px';
        resizerOverlay.style.fontFamily = 'sans-serif';
        resizerOverlay.style.userSelect = 'none';
        
        resizerOverlay.innerHTML = `
            <span style="font-weight: bold; color: #0078d4;">이미지 너비:</span>
            <input type="text" id="resizer-width-input" style="width: 55px; padding: 2px 4px; border: 1px solid #555; background: #222; color: #fff; border-radius: 4px; text-align: center;" />
            <button id="resizer-btn-auto" style="padding: 2px 6px; border: 1px solid #555; background: #444; color: #fff; border-radius: 4px; cursor: pointer;">원본</button>
            <button id="resizer-btn-50" style="padding: 2px 6px; border: 1px solid #555; background: #444; color: #fff; border-radius: 4px; cursor: pointer;">50%</button>
            <button id="resizer-btn-100" style="padding: 2px 6px; border: 1px solid #555; background: #444; color: #fff; border-radius: 4px; cursor: pointer;">100%</button>
            <button id="resizer-btn-apply" style="padding: 2px 8px; border: none; background: #0078d4; color: #fff; border-radius: 4px; cursor: pointer; font-weight: bold;">적용</button>
        `;
        document.body.appendChild(resizerOverlay);
        
        // Auto Button
        document.getElementById('resizer-btn-auto').addEventListener('click', function() {
            if (currentImage) {
                currentImage.style.width = '';
                currentImage.style.height = '';
                currentImage.removeAttribute('width');
                currentImage.removeAttribute('height');
                updateResizerInput();
                notifyContentChanged();
            }
        });
        
        // 50% Button
        document.getElementById('resizer-btn-50').addEventListener('click', function() {
            if (currentImage) {
                currentImage.style.width = '50%';
                currentImage.style.height = 'auto';
                currentImage.removeAttribute('width');
                currentImage.removeAttribute('height');
                updateResizerInput();
                notifyContentChanged();
            }
        });

        // 100% Button
        document.getElementById('resizer-btn-100').addEventListener('click', function() {
            if (currentImage) {
                currentImage.style.width = '100%';
                currentImage.style.height = 'auto';
                currentImage.removeAttribute('width');
                currentImage.removeAttribute('height');
                updateResizerInput();
                notifyContentChanged();
            }
        });

        // Apply Button
        document.getElementById('resizer-btn-apply').addEventListener('click', function() {
            if (currentImage) {
                var widthVal = document.getElementById('resizer-width-input').value.trim();
                if (widthVal) {
                    if (/^\d+$/.test(widthVal)) {
                        currentImage.setAttribute('width', widthVal);
                        widthVal += 'px';
                    } else if (widthVal.endsWith('px')) {
                        currentImage.setAttribute('width', widthVal.replace('px', ''));
                    } else {
                        currentImage.removeAttribute('width');
                    }
                    currentImage.style.width = widthVal;
                    currentImage.style.height = 'auto';
                    currentImage.removeAttribute('height');
                    notifyContentChanged();
                }
            }
        });
        
        // Enter trigger
        document.getElementById('resizer-width-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('resizer-btn-apply').click();
            }
        });
    }
    
    // Position overlay below the image
    const rect = img.getBoundingClientRect();
    const scrollY = window.scrollY || window.pageYOffset;
    const scrollX = window.scrollX || window.pageXOffset;
    resizerOverlay.style.top = (rect.bottom + scrollY + 6) + 'px';
    resizerOverlay.style.left = Math.max(10, rect.left + scrollX + (rect.width / 2) - 130) + 'px';
    resizerOverlay.style.display = 'flex';
    
    updateResizerInput();
}

function updateResizerInput() {
    if (currentImage) {
        var widthInput = document.getElementById('resizer-width-input');
        if (widthInput) {
            widthInput.value = currentImage.style.width || currentImage.width || "";
        }
    }
}

function hideImageResizer() {
    if (resizerOverlay) {
        resizerOverlay.style.display = 'none';
    }
    currentImage = null;
}

// Table & Cell Resizer Overlay Setup and Positioners
function showTableResizer(table, cell, row) {
    currentTable = table;
    currentCell = cell;
    currentRow = row;
    
    if (!tableResizerOverlay) {
        tableResizerOverlay = document.createElement('div');
        tableResizerOverlay.id = 'table-resizer-overlay';
        tableResizerOverlay.style.position = 'absolute';
        tableResizerOverlay.style.background = 'rgba(30, 30, 30, 0.95)';
        tableResizerOverlay.style.color = '#ffffff';
        tableResizerOverlay.style.padding = '8px 12px';
        tableResizerOverlay.style.borderRadius = '6px';
        tableResizerOverlay.style.boxShadow = '0 4px 12px rgba(0,0,0,0.25)';
        tableResizerOverlay.style.display = 'flex';
        tableResizerOverlay.style.alignItems = 'center';
        tableResizerOverlay.style.gap = '8px';
        tableResizerOverlay.style.zIndex = '1000';
        tableResizerOverlay.style.fontSize = '12px';
        tableResizerOverlay.style.fontFamily = 'sans-serif';
        tableResizerOverlay.style.userSelect = 'none';
        
        tableResizerOverlay.innerHTML = `
            <span style="font-weight: bold; color: #0078d4;">표 너비:</span>
            <input type="text" id="table-width-input" style="width: 55px; padding: 2px 4px; border: 1px solid #555; background: #222; color: #fff; border-radius: 4px; text-align: center;" />
            
            <span style="color: #666; margin: 0 4px;">|</span>
            
            <span style="font-weight: bold; color: #0078d4;">셀 가로:</span>
            <input type="text" id="cell-width-input" style="width: 55px; padding: 2px 4px; border: 1px solid #555; background: #222; color: #fff; border-radius: 4px; text-align: center;" />
            
            <span style="color: #666; margin: 0 4px;">|</span>
            
            <span style="font-weight: bold; color: #0078d4;">행 높이:</span>
            <input type="text" id="row-height-input" style="width: 55px; padding: 2px 4px; border: 1px solid #555; background: #222; color: #fff; border-radius: 4px; text-align: center;" />
            
            <button id="table-resizer-apply" style="padding: 2px 10px; margin-left: 6px; border: none; background: #0078d4; color: #fff; border-radius: 4px; cursor: pointer; font-weight: bold;">적용</button>
        `;
        document.body.appendChild(tableResizerOverlay);
        
        document.getElementById('table-resizer-apply').addEventListener('click', function() {
            var changed = false;
            
            // 1. Table Width
            if (currentTable) {
                var tableWidth = document.getElementById('table-width-input').value.trim();
                if (tableWidth) {
                    if (/^\d+$/.test(tableWidth)) {
                        currentTable.setAttribute('width', tableWidth);
                        tableWidth += 'px';
                    } else if (tableWidth.endsWith('px')) {
                        currentTable.setAttribute('width', tableWidth.replace('px', ''));
                    } else {
                        currentTable.removeAttribute('width');
                    }
                    currentTable.style.width = tableWidth;
                    changed = true;
                }
            }
            
            // 2. Cell Width
            if (currentCell) {
                var cellWidth = document.getElementById('cell-width-input').value.trim();
                if (cellWidth) {
                    if (/^\d+$/.test(cellWidth)) {
                        currentCell.setAttribute('width', cellWidth);
                        cellWidth += 'px';
                    } else if (cellWidth.endsWith('px')) {
                        currentCell.setAttribute('width', cellWidth.replace('px', ''));
                    } else {
                        currentCell.removeAttribute('width');
                    }
                    currentCell.style.width = cellWidth;
                    changed = true;
                }
            }
            
            // 3. Row Height
            if (currentRow) {
                var rowHeight = document.getElementById('row-height-input').value.trim();
                if (rowHeight) {
                    if (/^\d+$/.test(rowHeight)) {
                        rowHeight += 'px';
                    }
                    currentRow.style.height = rowHeight;
                    
                    // Apply to row cells for native rendering compatibility in Outlook
                    var cells = currentRow.querySelectorAll('td, th');
                    for (var c of cells) {
                        c.style.height = rowHeight;
                        c.setAttribute('height', rowHeight.replace('px', ''));
                    }
                    changed = true;
                }
            }
            
            if (changed) {
                notifyContentChanged();
            }
        });
        
        // Enter triggers
        var inputIds = ['table-width-input', 'cell-width-input', 'row-height-input'];
        inputIds.forEach(function(id) {
            document.getElementById(id).addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    document.getElementById('table-resizer-apply').click();
                }
            });
        });
    }
    
    // Position below the clicked cell
    const rect = cell.getBoundingClientRect();
    const scrollY = window.scrollY || window.pageYOffset;
    const scrollX = window.scrollX || window.pageXOffset;
    tableResizerOverlay.style.top = (rect.bottom + scrollY + 6) + 'px';
    tableResizerOverlay.style.left = Math.max(10, rect.left + scrollX + (rect.width / 2) - 170) + 'px';
    tableResizerOverlay.style.display = 'flex';
    
    // Populate current values
    document.getElementById('table-width-input').value = table.style.width || table.getAttribute('width') || "";
    document.getElementById('cell-width-input').value = cell.style.width || cell.getAttribute('width') || "";
    document.getElementById('row-height-input').value = row.style.height || cell.style.height || cell.getAttribute('height') || "";
}

function hideTableResizer() {
    if (tableResizerOverlay) {
        tableResizerOverlay.style.display = 'none';
    }
    currentTable = null;
    currentCell = null;
    currentRow = null;
}

// Bind scroll event to hide overlays
editor.addEventListener('scroll', function() {
    hideImageResizer();
    hideTableResizer();
});
