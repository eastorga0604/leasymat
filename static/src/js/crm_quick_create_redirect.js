/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { KanbanRecordQuickCreate } from "@web/views/kanban/kanban_record_quick_create";
import { useService } from "@web/core/utils/hooks";

patch(KanbanRecordQuickCreate.prototype, {
    setup() {
        super.setup?.();

        const actionService = useService("action");

        const originalOnValidate = this.props.onValidate;
        this.props.onValidate = async (resId, mode) => {
            const kanbanContainer = document.querySelector('.o_kanban_renderer');
            if (!kanbanContainer) {
                console.warn("⚠️ Kanban container not found.");
                return await originalOnValidate(resId, mode);
            }

            const initialCount = kanbanContainer.querySelectorAll('.o_kanban_record').length;
            console.log("📋 Initial Kanban record count:", initialCount);

            await originalOnValidate(resId, mode);

            const observer = new MutationObserver(() => {
                const newCount = kanbanContainer.querySelectorAll('.o_kanban_record').length;
                console.log("📈 New Kanban record count:", newCount);

                if (newCount > initialCount) {
                    observer.disconnect();
                    console.log("🎯 New record confirmed. Opening form for:", resId);

                    setTimeout(() => {
                        actionService.doAction({
                            type: 'ir.actions.act_window',
                            res_model: 'crm.lead',
                            res_id: resId,
                            views: [[false, 'form']],
                            target: 'current',
                            context: { default_type: 'opportunity' },
                        });
                    }, 100);
                }
            });

            observer.observe(kanbanContainer, { childList: true, subtree: true });

            // Optional fallback timeout
            setTimeout(() => {
                observer.disconnect();
            }, 3000);
        };
    }
});