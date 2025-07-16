/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $KnowledgeSearchResponse = {
    properties: {
        results: {
            type: 'array',
            contains: {
                type: 'KnowledgeSearchResult',
            },
            isRequired: true,
        },
    },
} as const;
