/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
document.addEventListener('DOMContentLoaded', () => {
    console.log("✅ DOMContentLoaded triggered!");

    const observer = new MutationObserver(mutationsList => {
        for (const mutation of mutationsList) {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.matches('ul.o-autocomplete--dropdown-menu')) {
                        console.log("✅ Autocomplete dropdown menu detected!");

                        const ulObserver = new MutationObserver(innerMutations => {
                            innerMutations.forEach(innerMutation => {
                                innerMutation.addedNodes.forEach(innerNode => {
                                    if (innerNode.nodeType === Node.ELEMENT_NODE) {
                                        // Remove 'Create' node
                                        if (innerNode.matches('li.o_m2o_dropdown_option_create')) {
                                            console.log("🔥 Removing 'Create' option dynamically...");
                                            innerNode.remove();
                                        }
                                        // Rename 'Create and edit...' node
                                        if (innerNode.matches('li.o_m2o_dropdown_option_create_edit')) {
                                            const aTag = innerNode.querySelector('a');
                                            if (aTag) {
                                                console.log("✏️ Renaming 'Create and edit...' dynamically...");
                                                aTag.textContent = _t('Create New Client');
                                            }
                                        }
                                    }
                                });
                            });
                        });

                        ulObserver.observe(node, { childList: true, subtree: true });

                        // Patch immediately on first render
                        node.querySelectorAll('li.o_m2o_dropdown_option_create').forEach(li => li.remove());
                        node.querySelectorAll('li.o_m2o_dropdown_option_create_edit a').forEach(a => {
                            a.textContent = _t('Create New Client');
                        });

                        console.log("✅ Initial patching complete inside dropdown.");
                    }
                }
            });
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
});
